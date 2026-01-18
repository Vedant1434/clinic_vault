from typing import Optional
from datetime import datetime
from enum import Enum
from sqlmodel import Field, SQLModel, Column, Index
from sqlalchemy import DateTime

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
    email: str = Field(unique=True, index=True, max_length=255)
    hashed_password: str = Field(max_length=255)
    full_name: str = Field(max_length=255, index=True)
    role: UserRole = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_column=Column(DateTime, default=datetime.utcnow))
    updated_at: datetime = Field(default_factory=datetime.utcnow, sa_column=Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow))
    
    # Doctor specific fields
    specialty: Optional[str] = Field(default=None, max_length=100, index=True)
    status: Optional[DoctorStatus] = Field(default=DoctorStatus.OFFLINE, index=True)
    
    # Additional user fields (encrypted for PHI)
    phone_enc: Optional[str] = None
    address_enc: Optional[str] = None
    date_of_birth_enc: Optional[str] = None
    
    # Indexes for better query performance
    __table_args__ = (
        Index('idx_user_role_status', 'role', 'status'),
        Index('idx_user_specialty_status', 'specialty', 'status'),
    )

class Consultation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="user.id", index=True)
    doctor_id: int = Field(foreign_key="user.id", index=True)
    specialty: str = Field(max_length=100, index=True)
    status: ConsultationStatus = Field(default=ConsultationStatus.PENDING_PAYMENT, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_column=Column(DateTime, default=datetime.utcnow, index=True))
    updated_at: datetime = Field(default_factory=datetime.utcnow, sa_column=Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow))
    started_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime, nullable=True))
    ended_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime, nullable=True))
    
    # Encrypted Fields (PHI)
    symptoms_enc: str 
    notes_enc: Optional[str] = None
    transcript_enc: Optional[str] = None  # Stores the full transcript
    
    # Payment information
    payment_amount: Optional[float] = None
    payment_status: Optional[str] = None
    payment_date: Optional[datetime] = Field(default=None, sa_column=Column(DateTime, nullable=True))
    
    # Indexes for better query performance
    __table_args__ = (
        Index('idx_consultation_patient_status', 'patient_id', 'status'),
        Index('idx_consultation_doctor_status', 'doctor_id', 'status'),
        Index('idx_consultation_status_created', 'status', 'created_at'),
        Index('idx_consultation_patient_created', 'patient_id', 'created_at'),
    )

class PrivacyLog(SQLModel, table=True):
    """Immutable Audit Trail for HIPAA Compliance"""
    id: Optional[int] = Field(default=None, primary_key=True)
    consultation_id: Optional[int] = Field(foreign_key="consultation.id", nullable=True, index=True)
    actor_id: Optional[int] = Field(foreign_key="user.id", index=True)
    actor_name: str = Field(max_length=255)
    action: str = Field(max_length=255, index=True)
    target_data: str 
    timestamp: datetime = Field(default_factory=datetime.utcnow, sa_column=Column(DateTime, default=datetime.utcnow, index=True))
    purpose: str = Field(max_length=255)
    ip_address: Optional[str] = Field(default=None, max_length=45)
    
    # Indexes for audit trail queries
    __table_args__ = (
        Index('idx_privacy_actor_timestamp', 'actor_id', 'timestamp'),
        Index('idx_privacy_consultation_timestamp', 'consultation_id', 'timestamp'),
        Index('idx_privacy_action_timestamp', 'action', 'timestamp'),
    )