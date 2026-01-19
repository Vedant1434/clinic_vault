"""
Test cases for workflow functionality (triage, consultation, billing)
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.main import app
from app.database import get_db
from app.models import User, Consultation, UserRole, DoctorStatus, ConsultationStatus
from app.security import pwd_context, create_access_token


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_db] = get_session_override
    client = TestClient(app=app, follow_redirects=False)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture(name="test_patient")
def test_patient_fixture(session: Session):
    patient = User(
        email="patient@example.com",
        hashed_password=pwd_context.hash("patient123"),
        full_name="Test Patient",
        role=UserRole.PATIENT
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)
    return patient


@pytest.fixture(name="test_doctor")
def test_doctor_fixture(session: Session):
    doctor = User(
        email="doctor@example.com",
        hashed_password=pwd_context.hash("doctor123"),
        full_name="Dr. Test",
        role=UserRole.DOCTOR,
        specialty="General",
        status=DoctorStatus.ONLINE
    )
    session.add(doctor)
    session.commit()
    session.refresh(doctor)
    return doctor


@pytest.fixture(name="authenticated_patient_client")
def authenticated_patient_client_fixture(client: TestClient, test_patient: User):
    """Create authenticated client for patient"""
    token = create_access_token(data={"sub": test_patient.email})
    client.cookies.set("access_token", f"Bearer {token}")
    return client


@pytest.fixture(name="authenticated_doctor_client")
def authenticated_doctor_client_fixture(client: TestClient, test_doctor: User):
    """Create authenticated client for doctor"""
    token = create_access_token(data={"sub": test_doctor.email})
    client.cookies.set("access_token", f"Bearer {token}")
    return client


class TestTriage:
    """Test triage functionality"""
    
    def test_start_triage_success(
        self, authenticated_patient_client: TestClient, test_patient: User, test_doctor: User, session: Session
    ):
        """Test successful triage start"""
        response = authenticated_patient_client.post(
            "/triage/start",
            data={
                "specialty": "General",
                "symptoms": "Headache and fever"
            }
        )
        assert response.status_code == 303
        
        # Verify consultation was created
        from sqlmodel import select
        consultation = session.exec(
            select(Consultation).where(Consultation.patient_id == test_patient.id)
        ).first()
        assert consultation is not None
        assert consultation.doctor_id == test_doctor.id
        assert consultation.status == ConsultationStatus.PENDING_PAYMENT
    
    def test_start_triage_no_doctor_available(
        self, authenticated_patient_client: TestClient, test_doctor: User, session: Session
    ):
        """Test triage when no doctor is available"""
        # Set doctor to offline
        test_doctor.status = DoctorStatus.OFFLINE
        session.add(test_doctor)
        session.commit()
        
        response = authenticated_patient_client.post(
            "/triage/start",
            data={
                "specialty": "General",
                "symptoms": "Headache and fever"
            },
            headers={"Accept": "application/json"}
        )
        assert response.status_code == 404
        assert "error" in response.json()
    
    def test_start_triage_unauthorized(self, client: TestClient):
        """Test triage without authentication"""
        response = client.post(
            "/triage/start",
            data={
                "specialty": "General",
                "symptoms": "Headache and fever"
            }
        )
        assert response.status_code in [401, 303]  # May redirect to login


class TestBilling:
    """Test billing functionality"""
    
    def test_billing_page_success(
        self, authenticated_patient_client: TestClient, test_patient: User, test_doctor: User, session: Session
    ):
        """Test accessing billing page"""
        # Create a consultation
        from app.security import encrypt_phi
        consultation = Consultation(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            specialty="General",
            status=ConsultationStatus.PENDING_PAYMENT,
            symptoms_enc=encrypt_phi("Headache")
        )
        session.add(consultation)
        session.commit()
        session.refresh(consultation)
        
        response = authenticated_patient_client.get(f"/billing/{consultation.id}")
        assert response.status_code == 200
    
    def test_billing_page_unauthorized(
        self, authenticated_patient_client: TestClient, test_doctor: User, session: Session
    ):
        """Test accessing billing page for another patient's consultation"""
        # Create a consultation with different patient
        from app.security import encrypt_phi
        other_patient = User(
            email="other@example.com",
            hashed_password=pwd_context.hash("password"),
            full_name="Other Patient",
            role=UserRole.PATIENT
        )
        session.add(other_patient)
        session.commit()
        
        consultation = Consultation(
            patient_id=other_patient.id,
            doctor_id=test_doctor.id,
            specialty="General",
            status=ConsultationStatus.PENDING_PAYMENT,
            symptoms_enc=encrypt_phi("Headache")
        )
        session.add(consultation)
        session.commit()
        session.refresh(consultation)
        
        response = authenticated_patient_client.get(f"/billing/{consultation.id}")
        assert response.status_code == 303  # Redirected
    
    def test_process_payment_success(
        self, authenticated_patient_client: TestClient, test_patient: User, test_doctor: User, session: Session
    ):
        """Test successful payment processing"""
        from app.security import encrypt_phi
        consultation = Consultation(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            specialty="General",
            status=ConsultationStatus.PENDING_PAYMENT,
            symptoms_enc=encrypt_phi("Headache")
        )
        session.add(consultation)
        session.commit()
        session.refresh(consultation)
        
        response = authenticated_patient_client.post(
            "/billing/process",
            data={
                "consultation_id": consultation.id,
                "outcome": "success"
            }
        )
        assert response.status_code == 303
        
        session.refresh(consultation)
        assert consultation.status == ConsultationStatus.ACTIVE


class TestConsultation:
    """Test consultation functionality"""
    
    def test_consultation_room_access(
        self, authenticated_patient_client: TestClient, test_patient: User, test_doctor: User, session: Session
    ):
        """Test accessing consultation room"""
        from app.security import encrypt_phi
        consultation = Consultation(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            specialty="General",
            status=ConsultationStatus.ACTIVE,
            symptoms_enc=encrypt_phi("Headache")
        )
        session.add(consultation)
        session.commit()
        session.refresh(consultation)
        
        response = authenticated_patient_client.get(f"/consultation/{consultation.id}")
        assert response.status_code == 200
    
    def test_consultation_room_unauthorized(
        self, authenticated_patient_client: TestClient, test_doctor: User, session: Session
    ):
        """Test accessing consultation room without authorization"""
        from app.security import encrypt_phi
        other_patient = User(
            email="other@example.com",
            hashed_password=pwd_context.hash("password"),
            full_name="Other Patient",
            role=UserRole.PATIENT
        )
        session.add(other_patient)
        session.commit()
        
        consultation = Consultation(
            patient_id=other_patient.id,
            doctor_id=test_doctor.id,
            specialty="General",
            status=ConsultationStatus.ACTIVE,
            symptoms_enc=encrypt_phi("Headache")
        )
        session.add(consultation)
        session.commit()
        session.refresh(consultation)
        
        response = authenticated_patient_client.get(f"/consultation/{consultation.id}")
        assert response.status_code == 403
    
    def test_save_notes(
        self, authenticated_doctor_client: TestClient, test_patient: User, test_doctor: User, session: Session
    ):
        """Test saving consultation notes"""
        from app.security import encrypt_phi
        consultation = Consultation(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            specialty="General",
            status=ConsultationStatus.ACTIVE,
            symptoms_enc=encrypt_phi("Headache")
        )
        session.add(consultation)
        session.commit()
        session.refresh(consultation)
        
        response = authenticated_doctor_client.post(
            "/consultation/notes",
            data={
                "consultation_id": consultation.id,
                "notes": "Patient shows signs of improvement"
            }
        )
        assert response.status_code == 303
        
        session.refresh(consultation)
        assert consultation.notes_enc is not None
    
    def test_end_consultation(
        self, authenticated_doctor_client: TestClient, test_patient: User, test_doctor: User, session: Session
    ):
        """Test ending consultation"""
        from app.security import encrypt_phi
        consultation = Consultation(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            specialty="General",
            status=ConsultationStatus.ACTIVE,
            symptoms_enc=encrypt_phi("Headache")
        )
        session.add(consultation)
        test_doctor.status = DoctorStatus.BUSY
        session.add(test_doctor)
        session.commit()
        session.refresh(consultation)
        
        response = authenticated_doctor_client.get(f"/consultation/end/{consultation.id}")
        assert response.status_code == 303
        
        session.refresh(consultation)
        assert consultation.status == ConsultationStatus.COMPLETED
        
        session.refresh(test_doctor)
        assert test_doctor.status == DoctorStatus.ONLINE


class TestTransfer:
    """Test consultation transfer functionality"""
    
    def test_get_available_doctors(
        self, authenticated_doctor_client: TestClient, test_patient: User, test_doctor: User, session: Session
    ):
        """Test getting available doctors for transfer"""
        from app.security import encrypt_phi
        consultation = Consultation(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            specialty="General",
            status=ConsultationStatus.ACTIVE,
            symptoms_enc=encrypt_phi("Headache")
        )
        session.add(consultation)
        session.commit()
        session.refresh(consultation)
        
        # Create another online doctor
        other_doctor = User(
            email="otherdoctor@example.com",
            hashed_password=pwd_context.hash("password"),
            full_name="Dr. Other",
            role=UserRole.DOCTOR,
            specialty="Cardiology",
            status=DoctorStatus.ONLINE
        )
        session.add(other_doctor)
        session.commit()
        
        response = authenticated_doctor_client.get(f"/consultation/{consultation.id}/available-doctors")
        assert response.status_code == 200
        data = response.json()
        assert "doctors" in data
        assert len(data["doctors"]) > 0
    
    def test_transfer_consultation(
        self, authenticated_doctor_client: TestClient, test_patient: User, test_doctor: User, session: Session
    ):
        """Test transferring consultation to another doctor"""
        from app.security import encrypt_phi
        consultation = Consultation(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            specialty="General",
            status=ConsultationStatus.ACTIVE,
            symptoms_enc=encrypt_phi("Headache")
        )
        session.add(consultation)
        test_doctor.status = DoctorStatus.BUSY
        session.add(test_doctor)
        session.commit()
        session.refresh(consultation)
        
        # Create another online doctor
        new_doctor = User(
            email="newdoctor@example.com",
            hashed_password=pwd_context.hash("password"),
            full_name="Dr. New",
            role=UserRole.DOCTOR,
            specialty="Cardiology",
            status=DoctorStatus.ONLINE
        )
        session.add(new_doctor)
        session.commit()
        session.refresh(new_doctor)
        
        old_doctor_id = consultation.doctor_id
        
        response = authenticated_doctor_client.post(
            "/consultation/transfer",
            data={
                "consultation_id": consultation.id,
                "new_doctor_id": new_doctor.id,
                "reason": "Emergency case requiring specialist"
            },
            headers={"Accept": "application/json"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        
        session.refresh(consultation)
        assert consultation.doctor_id == new_doctor.id
        
        session.refresh(test_doctor)
        assert test_doctor.status == DoctorStatus.ONLINE
        
        session.refresh(new_doctor)
        assert new_doctor.status == DoctorStatus.BUSY
    
    def test_transfer_unauthorized(
        self, authenticated_patient_client: TestClient, test_patient: User, test_doctor: User, session: Session
    ):
        """Test that patients cannot transfer consultations"""
        from app.security import encrypt_phi
        consultation = Consultation(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            specialty="General",
            status=ConsultationStatus.ACTIVE,
            symptoms_enc=encrypt_phi("Headache")
        )
        session.add(consultation)
        session.commit()
        session.refresh(consultation)
        
        response = authenticated_patient_client.get(f"/consultation/{consultation.id}/available-doctors")
        assert response.status_code == 403
    
    def test_transfer_to_unavailable_doctor(
        self, authenticated_doctor_client: TestClient, test_patient: User, test_doctor: User, session: Session
    ):
        """Test transferring to an unavailable doctor"""
        from app.security import encrypt_phi
        consultation = Consultation(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            specialty="General",
            status=ConsultationStatus.ACTIVE,
            symptoms_enc=encrypt_phi("Headache")
        )
        session.add(consultation)
        test_doctor.status = DoctorStatus.BUSY
        session.add(test_doctor)
        session.commit()
        session.refresh(consultation)
        
        # Create an offline doctor
        offline_doctor = User(
            email="offlinedoctor@example.com",
            hashed_password=pwd_context.hash("password"),
            full_name="Dr. Offline",
            role=UserRole.DOCTOR,
            specialty="Cardiology",
            status=DoctorStatus.OFFLINE
        )
        session.add(offline_doctor)
        session.commit()
        session.refresh(offline_doctor)
        
        response = authenticated_doctor_client.post(
            "/consultation/transfer",
            data={
                "consultation_id": consultation.id,
                "new_doctor_id": offline_doctor.id,
                "reason": "Test transfer"
            },
            headers={"Accept": "application/json"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "error" in data

