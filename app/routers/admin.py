from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlmodel import Session, select

from app.database import get_db
from app.models import User, UserRole, DoctorStatus, PrivacyLog, Consultation, ConsultationStatus
from app.security import get_current_user_from_token, pwd_context, audit_log
from app.templates import render_template

router = APIRouter()

@router.post("/admin/add_doctor")
async def add_doctor(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    specialty: str = Form(...),
    session: Session = Depends(get_db)
):
    # Get token from cookies (cookie-based authentication)
    token = request.cookies.get("access_token")
    if not token:
        if request.headers.get("accept") == "application/json":
            return JSONResponse(status_code=401, content={"error": "Unauthorized"})
        return RedirectResponse("/")
    
    try:
        admin = await get_current_user_from_token(token, session)
    except Exception:
        if request.headers.get("accept") == "application/json":
            return JSONResponse(status_code=401, content={"error": "Invalid token"})
        return RedirectResponse("/")
    
    if admin.role != UserRole.ADMIN:
        if request.headers.get("accept") == "application/json":
            return JSONResponse(status_code=403, content={"error": "Only administrators can add doctors"})
        return HTMLResponse("Unauthorized: Only administrators can add doctors", status_code=403)
    
    # Check if email already exists
    existing = session.exec(select(User).where(User.email == email)).first()
    if existing:
        if request.headers.get("accept") == "application/json":
            return JSONResponse(status_code=400, content={"error": "Email already registered"})
        # Reload dashboard with error message
        doctors = session.exec(select(User).where(User.role == UserRole.DOCTOR)).all()
        logs = session.exec(select(PrivacyLog).order_by(PrivacyLog.timestamp.desc()).limit(50)).all()
        return render_template("dashboard_admin", {
            "request": request,
            "user": admin,
            "doctors": doctors,
            "logs": logs,
            "error": "Email already registered"
        })
    
    new_doc = User(
        email=email,
        hashed_password=pwd_context.hash(password),
        full_name=full_name,
        role=UserRole.DOCTOR,
        specialty=specialty,
        status=DoctorStatus.OFFLINE
    )
    session.add(new_doc)
    session.commit()
    session.refresh(new_doc)
    audit_log(session, admin, "Onboarded New Doctor", f"Staff: {full_name}", "Staff Management")
    
    if request.headers.get("accept") == "application/json":
        return JSONResponse(content={"success": True, "message": f"Doctor {full_name} added successfully"})
    
    return RedirectResponse("/dashboard", status_code=303)

@router.post("/admin/remove_doctor")
async def remove_doctor(
    request: Request,
    doctor_id: int = Form(...),
    session: Session = Depends(get_db)
):
    """Remove a doctor from the system"""
    token = request.cookies.get("access_token")
    if not token:
        if request.headers.get("accept") == "application/json":
            return JSONResponse(status_code=401, content={"error": "Unauthorized"})
        return RedirectResponse("/")
    
    try:
        admin = await get_current_user_from_token(token, session)
    except Exception:
        if request.headers.get("accept") == "application/json":
            return JSONResponse(status_code=401, content={"error": "Invalid token"})
        return RedirectResponse("/")
    
    if admin.role != UserRole.ADMIN:
        if request.headers.get("accept") == "application/json":
            return JSONResponse(status_code=403, content={"error": "Only administrators can remove doctors"})
        return HTMLResponse("Unauthorized: Only administrators can remove doctors", status_code=403)
    
    # Get the doctor to remove
    doctor = session.get(User, doctor_id)
    if not doctor:
        if request.headers.get("accept") == "application/json":
            return JSONResponse(status_code=404, content={"error": "Doctor not found"})
        doctors = session.exec(select(User).where(User.role == UserRole.DOCTOR)).all()
        logs = session.exec(select(PrivacyLog).order_by(PrivacyLog.timestamp.desc()).limit(50)).all()
        return render_template("dashboard_admin", {
            "request": request,
            "user": admin,
            "doctors": doctors,
            "logs": logs,
            "error": "Doctor not found"
        })
    
    if doctor.role != UserRole.DOCTOR:
        if request.headers.get("accept") == "application/json":
            return JSONResponse(status_code=400, content={"error": "User is not a doctor"})
        doctors = session.exec(select(User).where(User.role == UserRole.DOCTOR)).all()
        logs = session.exec(select(PrivacyLog).order_by(PrivacyLog.timestamp.desc()).limit(50)).all()
        return render_template("dashboard_admin", {
            "request": request,
            "user": admin,
            "doctors": doctors,
            "logs": logs,
            "error": "User is not a doctor"
        })
    
    # Check if doctor has active consultations
    active_consultations = session.exec(select(Consultation).where(
        Consultation.doctor_id == doctor_id,
        Consultation.status.in_([ConsultationStatus.ACTIVE, ConsultationStatus.PENDING_PAYMENT])
    )).all()
    
    if active_consultations:
        if request.headers.get("accept") == "application/json":
            return JSONResponse(status_code=400, content={
                "error": f"Cannot remove doctor with {len(active_consultations)} active consultation(s)"
            })
        doctors = session.exec(select(User).where(User.role == UserRole.DOCTOR)).all()
        logs = session.exec(select(PrivacyLog).order_by(PrivacyLog.timestamp.desc()).limit(50)).all()
        return render_template("dashboard_admin", {
            "request": request,
            "user": admin,
            "doctors": doctors,
            "logs": logs,
            "error": f"Cannot remove doctor with {len(active_consultations)} active consultation(s)"
        })
    
    doctor_name = doctor.full_name
    session.delete(doctor)
    session.commit()
    
    audit_log(session, admin, "Removed Doctor", f"Staff: {doctor_name}", "Staff Management")
    
    if request.headers.get("accept") == "application/json":
        return JSONResponse(content={"success": True, "message": f"Doctor {doctor_name} removed successfully"})
    
    return RedirectResponse("/dashboard", status_code=303)

@router.post("/admin/delete_logs")
async def delete_logs(
    request: Request,
    log_ids: str = Form(None),  # Comma-separated list of log IDs, or None for all
    session: Session = Depends(get_db)
):
    """Delete privacy logs (admin only)"""
    token = request.cookies.get("access_token")
    if not token:
        if request.headers.get("accept") == "application/json":
            return JSONResponse(status_code=401, content={"error": "Unauthorized"})
        return RedirectResponse("/")
    
    try:
        admin = await get_current_user_from_token(token, session)
    except Exception:
        if request.headers.get("accept") == "application/json":
            return JSONResponse(status_code=401, content={"error": "Invalid token"})
        return RedirectResponse("/")
    
    if admin.role != UserRole.ADMIN:
        if request.headers.get("accept") == "application/json":
            return JSONResponse(status_code=403, content={"error": "Only administrators can delete logs"})
        return HTMLResponse("Unauthorized: Only administrators can delete logs", status_code=403)
    
    deleted_count = 0
    
    if log_ids:
        # Delete specific logs
        log_id_list = [int(id.strip()) for id in log_ids.split(",") if id.strip().isdigit()]
        for log_id in log_id_list:
            log = session.get(PrivacyLog, log_id)
            if log:
                session.delete(log)
                deleted_count += 1
    else:
        # Delete all logs (admin can choose to clear all)
        all_logs = session.exec(select(PrivacyLog)).all()
        for log in all_logs:
            session.delete(log)
            deleted_count += 1
    
    session.commit()
    audit_log(session, admin, "Deleted Privacy Logs", f"Deleted {deleted_count} log(s)", "System Maintenance")
    
    if request.headers.get("accept") == "application/json":
        return JSONResponse(content={
            "success": True,
            "message": f"Successfully deleted {deleted_count} log(s)"
        })
    
    return RedirectResponse("/dashboard", status_code=303)