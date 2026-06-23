import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from app.database import get_db
from app.models import Hub, VolunteerProfile, WelfareCase, CitizenProfile, CitizenTimeline, User
from app.schemas import (
    HubCreate,
    HubResponse,
    VolunteerProfileCreate,
    VolunteerProfileResponse,
    WelfareCaseCreate,
    WelfareCaseUpdate,
    WelfareCaseResponse
)

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/api/volunteer-ops", tags=["Volunteer & Hub Operations"])

@router.post("/hubs", response_model=HubResponse, status_code=status.HTTP_201_CREATED)
def create_hub(payload: HubCreate, db: Session = Depends(get_db)):
    """
    Register a Central or Local Hub.
    """
    existing = db.query(Hub).filter(Hub.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Hub name already registered.")
        
    db_hub = Hub(
        name=payload.name,
        hub_type=payload.hub_type,
        district=payload.district,
        parent_hub_id=payload.parent_hub_id
    )
    db.add(db_hub)
    db.commit()
    db.refresh(db_hub)
    return db_hub

@router.get("/hubs", response_model=List[HubResponse])
def get_hubs(db: Session = Depends(get_db)):
    """
    List all registered hubs.
    """
    return db.query(Hub).all()

@router.post("/volunteers", response_model=VolunteerProfileResponse, status_code=status.HTTP_201_CREATED)
def create_or_update_volunteer(payload: VolunteerProfileCreate, db: Session = Depends(get_db)):
    """
    Register or update a volunteer profile.
    """
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User account not found.")

    vol = db.query(VolunteerProfile).filter(VolunteerProfile.user_id == payload.user_id).first()
    if vol:
        # Update existing
        vol.contact_phone = payload.contact_phone
        vol.district = payload.district
        if payload.availability is not None:
            vol.availability = payload.availability
        vol.hub_id = payload.hub_id
    else:
        # Create new
        vol = VolunteerProfile(
            user_id=payload.user_id,
            contact_phone=payload.contact_phone,
            district=payload.district,
            availability=payload.availability if payload.availability is not None else True,
            hub_id=payload.hub_id
        )
        db.add(vol)

    db.commit()
    db.refresh(vol)
    return vol

@router.get("/volunteers/me", response_model=VolunteerProfileResponse)
def get_my_profile(request: Request, db: Session = Depends(get_db)):
    """
    Get the volunteer profile associated with the currently authenticated user.
    """
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required.")
        
    vol = db.query(VolunteerProfile).filter(VolunteerProfile.user_id == int(user_id)).first()
    if not vol:
        raise HTTPException(status_code=404, detail="Volunteer profile not found.")
    return vol

@router.post("/cases", response_model=WelfareCaseResponse, status_code=status.HTTP_201_CREATED)
def create_case(payload: WelfareCaseCreate, db: Session = Depends(get_db)):
    """
    Register a new case and run the Assignment Engine to match it to a volunteer.
    Assignments are load-balanced based on:
    1. Geography: Citizen district == Volunteer district.
    2. Availability: Volunteer availability is True.
    3. Workload: Least number of active cases.
    """
    citizen = db.query(CitizenProfile).filter(CitizenProfile.id == payload.citizen_id).first()
    if not citizen:
        raise HTTPException(status_code=404, detail="Citizen profile not found.")

    # 1. Assignment Engine
    matched_vol_id = None
    assigned_status = "Unassigned"
    
    if citizen.district:
        # Query available volunteers in the same district
        candidates = db.query(VolunteerProfile).filter(
            VolunteerProfile.district.ilike(citizen.district),
            VolunteerProfile.availability == True
        ).all()
        
        if candidates:
            # Find the volunteer with the lowest active cases (status != Resolved)
            least_workload = None
            selected_vol = None
            
            for vol in candidates:
                active_cases_count = db.query(WelfareCase).filter(
                    WelfareCase.volunteer_id == vol.id,
                    WelfareCase.status != "Resolved"
                ).count()
                
                if least_workload is None or active_cases_count < least_workload:
                    least_workload = active_cases_count
                    selected_vol = vol
            
            if selected_vol:
                matched_vol_id = selected_vol.id
                assigned_status = "Assigned"

    db_case = WelfareCase(
        citizen_id=payload.citizen_id,
        volunteer_id=matched_vol_id,
        title=payload.title,
        description=payload.description,
        status=assigned_status,
        upcoming_visit_date=payload.upcoming_visit_date,
        follow_up_tasks=payload.follow_up_tasks
    )
    
    db.add(db_case)
    db.commit()
    db.refresh(db_case)

    # 2. Add Timeline event to Citizen CRM timeline
    timeline_desc = f"New Case created: '{payload.title}'."
    if matched_vol_id:
        vol_user = db.query(User).join(VolunteerProfile).filter(VolunteerProfile.id == matched_vol_id).first()
        timeline_desc += f" Automatically assigned to volunteer '{vol_user.username}' (District: {citizen.district})."
    else:
        timeline_desc += " Case remains unassigned (No available volunteers in the district)."
        
    timeline_event = CitizenTimeline(
        citizen_id=citizen.id,
        event_type="Cases Created",
        description=timeline_desc
    )
    db.add(timeline_event)
    db.commit()
    db.refresh(db_case)

    return db_case

@router.get("/cases/assigned", response_model=List[WelfareCaseResponse])
def get_assigned_cases(request: Request, db: Session = Depends(get_db)):
    """
    Get cases assigned to the currently authenticated volunteer.
    """
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required.")
        
    vol = db.query(VolunteerProfile).filter(VolunteerProfile.user_id == int(user_id)).first()
    if not vol:
        return []
        
    return db.query(WelfareCase).filter(WelfareCase.volunteer_id == vol.id).order_by(WelfareCase.created_at.desc()).all()

@router.put("/cases/{case_id}", response_model=WelfareCaseResponse)
def update_case(case_id: int, payload: WelfareCaseUpdate, db: Session = Depends(get_db)):
    """
    Update details of a welfare case (status, checklist tasks, or volunteer ID).
    Automatically fires timeline updates.
    """
    db_case = db.query(WelfareCase).filter(WelfareCase.id == case_id).first()
    if not db_case:
        raise HTTPException(status_code=404, detail="Welfare case not found.")

    old_status = db_case.status
    old_visit_date = db_case.upcoming_visit_date

    # Update fields
    update_data = payload.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(db_case, k, v)

    db.commit()
    db.refresh(db_case)

    # Automatically generate citizen timeline audit trails
    timeline_desc = ""
    event_type = None

    if payload.status and payload.status != old_status:
        if payload.status == "Assigned":
            event_type = "Cases Created"
            vol_user = db.query(User).join(VolunteerProfile).filter(VolunteerProfile.id == db_case.volunteer_id).first()
            timeline_desc = f"Case '{db_case.title}' assigned to volunteer '{vol_user.username if vol_user else 'Unknown'}'."
        elif payload.status == "Visit Scheduled":
            event_type = "Volunteer Visit"
            timeline_desc = f"Home visit scheduled for case '{db_case.title}'."
            if db_case.upcoming_visit_date:
                timeline_desc += f" Scheduled Date: {db_case.upcoming_visit_date.strftime('%Y-%m-%d %H:%M')}."
        elif payload.status == "Resolved":
            event_type = "Resolutions"
            timeline_desc = f"Case '{db_case.title}' has been successfully resolved and closed."

    elif payload.upcoming_visit_date and payload.upcoming_visit_date != old_visit_date:
        event_type = "Volunteer Visit"
        timeline_desc = f"Home visit scheduled or modified for case '{db_case.title}'. Date: {db_case.upcoming_visit_date.strftime('%Y-%m-%d %H:%M')}."

    if event_type and timeline_desc:
        timeline_event = CitizenTimeline(
            citizen_id=db_case.citizen_id,
            event_type=event_type,
            description=timeline_desc
        )
        db.add(timeline_event)
        db.commit()
        db.refresh(db_case)

    return db_case
