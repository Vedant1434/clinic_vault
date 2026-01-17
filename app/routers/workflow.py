import shutil
import os
import json
import uuid
from typing import List, Dict
from fastapi import APIRouter, Depends, Form, Request, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session, select, or_

from app.database import get_db
from app.models import User, Consultation, ConsultationStatus, DoctorStatus, UserRole, PrivacyLog
from app.security import get_current_user, encrypt_phi, decrypt_phi, audit_log
from app.templates import render_template
from app.transcription import transcribe_audio_chunk

router = APIRouter()

# --- Dashboard ---
@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, session: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token: return RedirectResponse("/")
    try:
        user = await get_current_user(token, session)
    except:
        return RedirectResponse("/")

    if user.role == UserRole.ADMIN:
        doctors = session.exec(select(User).where(User.role == UserRole.DOCTOR)).all()
        logs = session.exec(select(PrivacyLog).order_by(PrivacyLog.timestamp.desc()).limit(50)).all()
        audit_log(session, user, "Viewed Admin Dashboard", "System Logs", "Administrative Review")
        return render_template("dashboard_admin", {"request": request, "user": user, "doctors": doctors, "logs": logs})

    elif user.role == UserRole.DOCTOR:
        consultations = session.exec(select(Consultation).where(
            Consultation.doctor_id == user.id,
            Consultation.status.in_([ConsultationStatus.ACTIVE, ConsultationStatus.PENDING_PAYMENT])
        )).all()
        return render_template("dashboard_doctor", {"request": request, "user": user, "consultations": consultations})

    elif user.role == UserRole.PATIENT:
        consult = session.exec(select(Consultation).where(
            Consultation.patient_id == user.id,
            Consultation.status.in_([ConsultationStatus.PENDING_PAYMENT, ConsultationStatus.ACTIVE])
        )).first()
        logs = session.exec(select(PrivacyLog).where(
            or_(PrivacyLog.actor_id == user.id, PrivacyLog.target_data != "System Internal")
        ).order_by(PrivacyLog.timestamp.desc()).limit(10)).all()
        audit_log(session, user, "Viewed Dashboard", "Privacy Timeline", "Self Review")
        return render_template("dashboard_patient", {"request": request, "user": user, "active_consultation": consult, "logs": logs})

# --- Triage ---
@router.post("/triage/start")
async def start_triage(
    request: Request, 
    specialty: str = Form(...), 
    symptoms: str = Form(...),
    session: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")
    user = await get_current_user(token, session)
    
    doctor = session.exec(select(User).where(
        User.role == UserRole.DOCTOR,
        User.specialty == specialty,
        User.status == DoctorStatus.ONLINE
    )).first()
    
    if not doctor:
        return HTMLResponse(f"<h3>No {specialty} doctors online. Please try again later.</h3><a href='/dashboard'>Back</a>")
    
    doctor.status = DoctorStatus.BUSY
    session.add(doctor)
    
    symptoms_enc = encrypt_phi(symptoms)
    consult = Consultation(
        patient_id=user.id,
        doctor_id=doctor.id,
        specialty=specialty,
        status=ConsultationStatus.PENDING_PAYMENT,
        symptoms_enc=symptoms_enc
    )
    session.add(consult)
    session.commit()
    session.refresh(consult)
    
    audit_log(session, user, "Submitted Triage Form", "Symptoms (Encrypted)", "Treatment Request", consult.id)
    audit_log(session, doctor, "System Assigned Patient", f"Patient #{user.id}", "Triage Algorithm", consult.id)
    
    return RedirectResponse("/dashboard", status_code=303)

# --- Billing ---
@router.get("/billing/{consult_id}", response_class=HTMLResponse)
async def billing_page(request: Request, consult_id: int, session: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    user = await get_current_user(token, session)
    consult = session.get(Consultation, consult_id)
    
    if not consult or consult.patient_id != user.id: return RedirectResponse("/dashboard")
    doctor = session.get(User, consult.doctor_id)
    return render_template("billing", {"request": request, "user": user, "consultation": consult, "doctor_name": doctor.full_name})

@router.post("/billing/process")
async def process_payment(consultation_id: int = Form(...), outcome: str = Form(...), session: Session = Depends(get_db)):
    consult = session.get(Consultation, consultation_id)
    doctor = session.get(User, consult.doctor_id)
    
    if outcome == "success":
        consult.status = ConsultationStatus.ACTIVE
        audit_log(session, doctor, "Authorized Access", "Medical Record", "Payment Confirmed", consult.id)
    else:
        consult.status = ConsultationStatus.CANCELLED
        doctor.status = DoctorStatus.ONLINE 
        
    session.add(consult)
    session.add(doctor)
    session.commit()
    return RedirectResponse("/dashboard", status_code=303)

# --- Consultation ---
@router.get("/consultation/{consult_id}", response_class=HTMLResponse)
async def consultation_room(request: Request, consult_id: int, session: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    user = await get_current_user(token, session)
    consult = session.get(Consultation, consult_id)
    
    if user.id not in [consult.patient_id, consult.doctor_id]: return HTMLResponse("Unauthorized Access", status_code=403)
    if consult.status != ConsultationStatus.ACTIVE: return RedirectResponse("/dashboard")
    
    symptoms = decrypt_phi(consult.symptoms_enc)
    
    # Fetch History (Previous Consultations)
    history = []
    if user.role == UserRole.DOCTOR:
        prev_consults = session.exec(select(Consultation).where(
            Consultation.patient_id == consult.patient_id,
            Consultation.id != consult.id,
            Consultation.status == ConsultationStatus.COMPLETED
        ).order_by(Consultation.created_at.desc())).all()
        
        for pc in prev_consults:
            doc = session.get(User, pc.doctor_id)
            history.append({
                "date": pc.created_at.strftime("%Y-%m-%d"),
                "doctor": doc.full_name if doc else "Unknown",
                "specialty": pc.specialty,
                "notes": decrypt_phi(pc.notes_enc) if pc.notes_enc else "No notes."
            })

    audit_log(session, user, "Entered Secure Room", "Video Stream", "Consultation", consult.id)
    return render_template("consultation", {
        "request": request, 
        "user": user, 
        "consultation": consult, 
        "symptoms_decrypted": symptoms,
        "history": history
    })

@router.post("/consultation/notes")
async def save_notes(request: Request, consultation_id: int = Form(...), notes: str = Form(...), session: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    user = await get_current_user(token, session)
    consult = session.get(Consultation, consultation_id)
    
    if user.role != UserRole.DOCTOR: return HTMLResponse("Only doctors can save notes")
    consult.notes_enc = encrypt_phi(notes)
    session.add(consult)
    session.commit()
    audit_log(session, user, "Appended Clinical Notes", "Medical Record", "Documentation", consult.id)
    return RedirectResponse(f"/consultation/{consultation_id}", status_code=303)

@router.get("/consultation/end/{consult_id}")
async def end_consultation(request: Request, consult_id: int, session: Session = Depends(get_db)):
    consult = session.get(Consultation, consult_id)
    doctor = session.get(User, consult.doctor_id)
    consult.status = ConsultationStatus.COMPLETED
    doctor.status = DoctorStatus.ONLINE 
    session.add(consult)
    session.add(doctor)
    session.commit()
    return RedirectResponse("/dashboard")

@router.get("/doctor/toggle_status")
async def toggle_status(request: Request, session: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    user = await get_current_user(token, session)
    if user.role == UserRole.DOCTOR:
        user.status = DoctorStatus.ONLINE if user.status == DoctorStatus.OFFLINE else DoctorStatus.OFFLINE
        session.add(user)
        session.commit()
    return RedirectResponse("/dashboard")

# --- WebSocket & Transcription ---
class ConnectionManager:
    def __init__(self): self.active_connections: Dict[int, List[WebSocket]] = {}
    async def connect(self, websocket: WebSocket, room_id: int):
        await websocket.accept()
        if room_id not in self.active_connections: self.active_connections[room_id] = []
        self.active_connections[room_id].append(websocket)
    
    def disconnect(self, websocket: WebSocket, room_id: int):
        if room_id in self.active_connections:
            self.active_connections[room_id].remove(websocket)

    async def broadcast(self, message: str, room_id: int):
        """Sends a message to all users in the room"""
        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]: 
                await connection.send_text(message)

    async def broadcast_except(self, message: str, room_id: int, sender_socket: WebSocket):
        """Sends a message to everyone EXCEPT the sender (for WebRTC signaling)"""
        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]:
                if connection != sender_socket:
                    await connection.send_text(message)

manager = ConnectionManager()

@router.websocket("/ws/{consult_id}/{user_id}")
async def websocket_endpoint(websocket: WebSocket, consult_id: int, user_id: int):
    await manager.connect(websocket, consult_id)
    try:
        while True:
            data = await websocket.receive_text()
            # Try to parse as JSON for WebRTC signaling
            try:
                msg_json = json.loads(data)
                if "type" in msg_json and msg_json["type"] in ["offer", "answer", "candidate"]:
                    # This is a WebRTC signaling message, broadcast to OTHER peer
                    await manager.broadcast_except(data, consult_id, websocket)
                else:
                    # Normal chat message (JSON formatted)
                    await manager.broadcast(data, consult_id)
            except json.JSONDecodeError:
                # Plain text fallback
                await manager.broadcast(f"User {user_id}: {data}", consult_id)
    except WebSocketDisconnect:
        manager.disconnect(websocket, consult_id)

@router.post("/consultation/transcribe")
async def transcribe_endpoint(
    consultation_id: int = Form(...),
    user_id: int = Form(...),
    audio_blob: UploadFile = File(...),
    session: Session = Depends(get_db)
):
    """Receives audio chunks, transcribes them, and broadcasts via WebSocket"""
    
    # Save temp file
    temp_filename = f"temp_{consultation_id}_{user_id}_{uuid.uuid4()}.webm"
    with open(temp_filename, "wb") as buffer:
        shutil.copyfileobj(audio_blob.file, buffer)
    
    # Run Faster Whisper
    text = transcribe_audio_chunk(temp_filename)
    
    if text:
        # Prepare JSON message
        msg = json.dumps({
            "type": "transcript",
            "user_id": user_id,
            "text": text
        })
        # Broadcast via WebSocket
        await manager.broadcast(msg, consultation_id)
        
        # Optionally: Append to DB transcript_enc (need to fetch, decrypt, append, encrypt, save)
        # For performance in this loop, we might skip DB save for every chunk or do it async.
        # Here we just audit log occasionally.
        
    return {"status": "ok", "text": text}