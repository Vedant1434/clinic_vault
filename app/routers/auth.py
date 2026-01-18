from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select
import re

from app.database import get_db
from app.models import User, UserRole, DoctorStatus
from app.security import create_access_token, pwd_context, audit_log
from app.templates import render_template

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def root():
    return render_template("login", {})

@router.get("/register", response_class=HTMLResponse)
async def register_page():
    return render_template("register", {})

@router.post("/auth/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_db)
):
    user = session.exec(select(User).where(User.email == username)).first()
    if not user or not pwd_context.verify(password, user.hashed_password):
        # Return JSON response for AJAX handling
        if request.headers.get("accept") == "application/json":
            return JSONResponse(
                status_code=400,
                content={"error": "Incorrect email or password"}
            )
        # Return HTML with error message for form submission
        return render_template("login", {
            "error": "Incorrect email or password. Please try again."
        })
    
    access_token = create_access_token(data={"sub": user.email})
    audit_log(session, user, "User Login", "Authentication System", "Access Control")
    
    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True)
    return response

@router.post("/auth/register")
async def register(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(None),
    session: Session = Depends(get_db)
):
    errors = []
    
    # Validate email format
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        errors.append("Invalid email format")
    
    # Validate password strength
    if len(password) < 6:
        errors.append("Password must be at least 6 characters long")
    
    # Check password confirmation if provided
    if password_confirm and password != password_confirm:
        errors.append("Passwords do not match")
    
    # Check if email already exists
    existing = session.exec(select(User).where(User.email == email)).first()
    if existing:
        errors.append("Email already registered")
    
    if errors:
        if request.headers.get("accept") == "application/json":
            return JSONResponse(
                status_code=400,
                content={"errors": errors}
            )
        return render_template("register", {
            "errors": errors,
            "full_name": full_name,
            "email": email
        })
    
    new_user = User(
        email=email,
        hashed_password=pwd_context.hash(password),
        full_name=full_name,
        role=UserRole.PATIENT
    )
    session.add(new_user)
    session.commit()
    audit_log(session, new_user, "Patient Registration", "User Account", "Onboarding")
    
    return RedirectResponse("/", status_code=303)

@router.post("/auth/seed")
async def seed_demo_data(session: Session = Depends(get_db)):
    # Seed some demo data
    admin = User(
        email="admin@hospital.com",
        hashed_password=pwd_context.hash("admin123"),
        full_name="System Administrator",
        role=UserRole.ADMIN
    )
    session.add(admin)
    
    doctor = User(
        email="doctor@hospital.com",
        hashed_password=pwd_context.hash("doctor123"),
        full_name="Dr. Smith",
        role=UserRole.DOCTOR,
        specialty="General",
        status=DoctorStatus.ONLINE
    )
    session.add(doctor)
    
    patient = User(
        email="patient@hospital.com",
        hashed_password=pwd_context.hash("patient123"),
        full_name="John Doe",
        role=UserRole.PATIENT
    )
    session.add(patient)
    
    session.commit()
    return RedirectResponse("/", status_code=303)

@router.get("/logout")
async def logout():
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie("access_token")
    return response