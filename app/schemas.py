from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime

class SurveyCreate(BaseModel):
    # Section A - Identity
    firstName: str
    middleName: Optional[str] = None
    lastName: str
    primaryMobile: str
    alternateMobile: Optional[str] = None
    dob: str
    age: Optional[str] = None
    aadhaarConsent: Optional[str] = None
    aadhaarNumber: Optional[str] = None
    gender: str
    maritalStatus: str
    religion: str
    socialCategory: str
    subCaste: Optional[str] = None
    residentialStatus: str
    houseNo: Optional[str] = None
    street: Optional[str] = None
    village: str
    mandal: Optional[str] = None
    district: str
    state: str
    pincode: Optional[str] = None
    durationAtAddress: Optional[str] = None

    # Section B - Household
    adults: Optional[str] = "0"
    childrenCount: Optional[str] = "0"
    seniors: Optional[str] = "0"
    familyStructure: str
    familyMembers: List[Dict[str, Any]] = []

    # Section C - Employment
    mainOccupation: str
    employmentNature: str
    secondaryIncome: List[str] = []
    empChallenges: List[str] = []

    # Section D - Income
    monthlyIncomeRange: str
    annualIncome: str
    bankAccount: str
    liquidSavings: Optional[str] = None
    insuranceCoverage: List[str] = []
    householdDebt: Dict[str, Any] = {}
    debtReasons: List[str] = []

    # Section E - Assets & Amenities
    housingType: str
    housingOwnership: str
    agriLand: str
    livestock: str
    twoWheelers: Optional[str] = "0"
    fourWheelers: Optional[str] = "0"
    smartphones: Optional[str] = "0"
    
    # Amenities (Part of Section E)
    amenity_electricity: Optional[str] = None
    amenity_drinkingWater: Optional[str] = None
    amenity_toilet: Optional[str] = None
    amenity_lpgGas: Optional[str] = None
    amenity_internet: Optional[str] = None

    # Section F - Education
    eduMembers: List[Dict[str, Any]] = []
    dropoutReasons: List[str] = []

    # Section G - Health
    chronicConditions: List[Dict[str, Any]] = []
    disabilities: List[Dict[str, Any]] = []
    healthcareAccess: List[str] = []
    healthChallenges: List[str] = []

    # Section H - Welfare
    currentSchemes: List[Dict[str, Any]] = []
    applicableSchemes: List[str] = []
    benefitsNotReceived: List[str] = []
    benefitsMostNeeded: List[str] = []

    # Section I - Digital Access & Docs
    hasSmartphone: str
    digitalAbility: Optional[str] = None
    doc_aadhaar_available: Optional[str] = None
    doc_aadhaar_valid: Optional[str] = None
    doc_pan_available: Optional[str] = None
    doc_pan_valid: Optional[str] = None
    doc_rationCard_available: Optional[str] = None
    doc_rationCard_valid: Optional[str] = None
    doc_incomeCert_available: Optional[str] = None
    doc_incomeCert_valid: Optional[str] = None
    doc_casteCert_available: Optional[str] = None
    doc_casteCert_valid: Optional[str] = None
    doc_disabilityCert_available: Optional[str] = None
    doc_disabilityCert_valid: Optional[str] = None
    doc_voterId_available: Optional[str] = None
    doc_voterId_valid: Optional[str] = None
    doc_bankPassbook_available: Optional[str] = None
    doc_bankPassbook_valid: Optional[str] = None

    # Section J - Community
    altContactName: Optional[str] = None
    altRelationship: Optional[str] = None
    altMobile: Optional[str] = None
    altOccupation: Optional[str] = None
    communityRole: List[str] = []
    willingToReceiveInfo: Optional[str] = None
    preferredComm: List[str] = []

    # Section K - Consent
    consentStatus: str
    signatureName: str
    consentDate: str
    surveyorName: str
    surveyorId: str
    surveyLocation: str
    additionalRemarks: Optional[str] = None

    # Survey Metadata (sent in payload)
    survey_language: Optional[str] = "en"
    submitted_at: Optional[str] = None
    sections_visited: List[str] = []


class SurveyUpdate(BaseModel):
    # Allow updating individual searchable columns or the entire payload
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    primaryMobile: Optional[str] = None
    dob: Optional[str] = None
    surveyorName: Optional[str] = None
    surveyorId: Optional[str] = None
    survey_language: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class SurveyResponse(BaseModel):
    id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    primary_mobile: Optional[str] = None
    dob: Optional[str] = None
    surveyor_name: Optional[str] = None
    surveyor_id: Optional[str] = None
    survey_language: Optional[str] = None
    submitted_at: Optional[datetime] = None
    data: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- RAG & Welfare Scheme schemas ---

class RawTextIngest(BaseModel):
    title: str
    content: str

class UrlIngest(BaseModel):
    title: str
    url: str

class SchemeCreate(BaseModel):
    scheme_name: str
    state: str
    category: str
    description: str
    benefits: Dict[str, Any]
    eligibility_rules: Dict[str, Any]
    required_documents: List[str]
    application_process: str
    source_page: Optional[int] = 1
    verification_status: Optional[str] = "UNVERIFIED"

class SchemeUpdate(BaseModel):
    scheme_name: Optional[str] = None
    state: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    benefits: Optional[Dict[str, Any]] = None
    eligibility_rules: Optional[Dict[str, Any]] = None
    required_documents: Optional[List[str]] = None
    application_process: Optional[str] = None
    source_page: Optional[int] = None
    verification_status: Optional[str] = None

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    profile: Dict[str, Any]
    question: str
    history: Optional[List[ChatMessage]] = []

class EligibleSchemeRecommendation(BaseModel):
    scheme_name: str
    eligibility_status: str
    eligibility_score: int
    why_recommended: str
    missing_documents: List[str]
    next_steps: str
    source_page: int
    verification_status: str

class ChatResponse(BaseModel):
    response: str
    recommendations: List[EligibleSchemeRecommendation]
    retrieved_sources: List[Dict[str, Any]]

