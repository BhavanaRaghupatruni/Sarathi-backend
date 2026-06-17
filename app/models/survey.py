from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.sql import func
from app.database import Base

class Survey(Base):
    __tablename__ = "surveys"

    id = Column(Integer, primary_key=True, index=True)
    
    # Top-level search and index columns (extracted from Section A / K)
    first_name = Column(String, index=True, nullable=True)
    last_name = Column(String, index=True, nullable=True)
    primary_mobile = Column(String, index=True, nullable=True)
    dob = Column(String, nullable=True)
    surveyor_name = Column(String, index=True, nullable=True)
    surveyor_id = Column(String, index=True, nullable=True)
    
    # Metadata
    survey_language = Column(String, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    
    # The complete survey questionnaire answers JSON document
    data = Column(JSON, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
