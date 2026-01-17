from typing import Optional
from datetime import datetime
from enum import Enum
from sqlmodel import Field, SQLModel

class UserRole(str, Enum):
    PATIENT = "patient"
    DOCTOR = "doctor"
    ADMIN = "admin"

class DoctorStatus(str, Enum):
    OFFLINE = "offline"
    ONLINE = "online"
    BUSY = "busy"

class ConsultationStatus(str, Enum):
    PENDING_PAYMENT = "pending_payment"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    full_name: str
    role: UserRole
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Doctor specific fields
    specialty: Optional[str] = None
    status: Optional[DoctorStatus] = Field(default=DoctorStatus.OFFLINE)

class Consultation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="user.id")
    doctor_id: int = Field(foreign_key="user.id")
    specialty: str
    status: ConsultationStatus = Field(default=ConsultationStatus.PENDING_PAYMENT)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Encrypted Fields (PHI)
    symptoms_enc: str 
    notes_enc: Optional[str] = None
    transcript_enc: Optional[str] = None # Stores the full transcript

class PrivacyLog(SQLModel, table=True):
    """Immutable Audit Trail for HIPAA Compliance"""
    id: Optional[int] = Field(default=None, primary_key=True)
    consultation_id: Optional[int] = Field(foreign_key="consultation.id", nullable=True)
    actor_id: Optional[int] = Field(foreign_key="user.id")
    actor_name: str
    action: str 
    target_data: str 
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    purpose: str