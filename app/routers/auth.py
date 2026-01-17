from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from app.database import get_db
from app.models import User, UserRole, DoctorStatus
from app.security import create_access_token, pwd_context, audit_log
from app.templates import render_template

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def root():
    return render_template("login", {})

@router.post("/auth/login")
async def login(
    request: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_db)
):
    user = session.exec(select(User).where(User.email == request.username)).first()
    if not user or not pwd_context.verify(request.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    access_token = create_access_token(data={"sub": user.email})
    audit_log(session, user, "User Login", "Authentication System", "Access Control")
    
    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True)
    return response

@router.post("/auth/register")
async def register(
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_db)
):
    existing = session.exec(select(User).where(User.email == email)).first()
    if existing:
        return HTMLResponse("Email already registered", status_code=400)
    
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