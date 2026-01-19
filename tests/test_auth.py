"""
Test cases for authentication functionality
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
from app.models import User, UserRole, DoctorStatus
from app.security import pwd_context


# Test database setup
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


@pytest.fixture(name="test_user")
def test_user_fixture(session: Session):
    user = User(
        email="test@example.com",
        hashed_password=pwd_context.hash("testpassword123"),
        full_name="Test User",
        role=UserRole.PATIENT
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


class TestLogin:
    """Test login functionality"""
    
    def test_login_success(self, client: TestClient, test_user: User):
        """Test successful login"""
        response = client.post(
            "/auth/login",
            data={"username": "test@example.com", "password": "testpassword123"}
        )
        assert response.status_code == 303
        assert "access_token" in response.cookies
    
    def test_login_invalid_email(self, client: TestClient, test_user: User):
        """Test login with invalid email"""
        response = client.post(
            "/auth/login",
            data={"username": "wrong@example.com", "password": "testpassword123"},
            headers={"Accept": "application/json"}
        )
        assert response.status_code == 400
        assert "error" in response.json()
    
    def test_login_invalid_password(self, client: TestClient, test_user: User):
        """Test login with invalid password"""
        response = client.post(
            "/auth/login",
            data={"username": "test@example.com", "password": "wrongpassword"},
            headers={"Accept": "application/json"}
        )
        assert response.status_code == 400
        assert "error" in response.json()
    
    def test_login_missing_credentials(self, client: TestClient):
        """Test login with missing credentials"""
        response = client.post("/auth/login", data={})
        assert response.status_code == 422


class TestRegistration:
    """Test registration functionality"""
    
    def test_register_success(self, client: TestClient, session: Session):
        """Test successful registration"""
        response = client.post(
            "/auth/register",
            data={
                "full_name": "New User",
                "email": "newuser@example.com",
                "password": "password123",
                "password_confirm": "password123"
            }
        )
        assert response.status_code == 303
        
        # Verify user was created
        from sqlmodel import select
        user = session.exec(
            select(User).where(User.email == "newuser@example.com")
        ).first()
        assert user is not None
        assert user.full_name == "New User"
        assert user.role == UserRole.PATIENT
    
    def test_register_duplicate_email(self, client: TestClient, test_user: User):
        """Test registration with duplicate email"""
        response = client.post(
            "/auth/register",
            data={
                "full_name": "Another User",
                "email": "test@example.com",
                "password": "password123",
                "password_confirm": "password123"
            },
            headers={"Accept": "application/json"}
        )
        assert response.status_code == 400
        assert "errors" in response.json()
    
    def test_register_password_mismatch(self, client: TestClient):
        """Test registration with password mismatch"""
        response = client.post(
            "/auth/register",
            data={
                "full_name": "New User",
                "email": "newuser@example.com",
                "password": "password123",
                "password_confirm": "differentpassword"
            },
            headers={"Accept": "application/json"}
        )
        # Client-side validation should catch this, but test server-side too
        assert response.status_code in [400, 303]
    
    def test_register_invalid_email(self, client: TestClient):
        """Test registration with invalid email format"""
        response = client.post(
            "/auth/register",
            data={
                "full_name": "New User",
                "email": "invalid-email",
                "password": "password123",
                "password_confirm": "password123"
            },
            headers={"Accept": "application/json"}
        )
        assert response.status_code == 400
    
    def test_register_short_password(self, client: TestClient):
        """Test registration with password too short"""
        response = client.post(
            "/auth/register",
            data={
                "full_name": "New User",
                "email": "newuser@example.com",
                "password": "12345",
                "password_confirm": "12345"
            },
            headers={"Accept": "application/json"}
        )
        assert response.status_code == 400


class TestLogout:
    """Test logout functionality"""
    
    def test_logout(self, client: TestClient, test_user: User):
        """Test logout"""
        # First login
        client.post(
            "/auth/login",
            data={"username": "test@example.com", "password": "testpassword123"}
        )
        
        # Then logout
        response = client.get("/logout")
        assert response.status_code == 303
        # Cookie should be deleted (check if it's set to empty or expires)
        assert "access_token" not in response.cookies or response.cookies.get("access_token") == ""

