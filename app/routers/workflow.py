import shutil
import os
import json
import uuid
from typing import List, Dict
from datetime import datetime
from fastapi import APIRouter, Depends, Form, Request, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlmodel import Session, select, or_

from app.database import get_db
from app.models import User, Consultation, ConsultationStatus, DoctorStatus, UserRole, PrivacyLog
from app.security import get_current_user, get_current_user_from_token, encrypt_phi, decrypt_phi, audit_log
from app.templates import render_template
from app.transcription import transcribe_audio_chunk

router = APIRouter()

# --- Dashboard ---
@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, session: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token: 
        return RedirectResponse("/")
    try:
        user = await get_current_user_from_token(token, session)
    except Exception as e:
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
    if not token:
        if request.headers.get("accept") == "application/json":
            return JSONResponse(status_code=401, content={"error": "Unauthorized"})
        return RedirectResponse("/", status_code=303)

    user = await get_current_user_from_token(token, session)
    
    doctor = session.exec(select(User).where(
        User.role == UserRole.DOCTOR,
        User.specialty == specialty,
        User.status == DoctorStatus.ONLINE
    )).first()
    
    if not doctor:
        # Return JSON response for AJAX handling
        if request.headers.get("accept") == "application/json":
            return JSONResponse(
                status_code=404,
                content={"error": f"No {specialty} doctors are currently available. Please try again later."}
            )
        # Return HTML with error message
        return render_template("dashboard_patient", {
            "request": request,
            "user": user,
            "active_consultation": None,
            "logs": [],
            "error": f"No {specialty} doctors are currently available. Please try again later."
        })
    
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
    if not token:
        return RedirectResponse("/")
    
    try:
        user = await get_current_user_from_token(token, session)
    except Exception:
        return RedirectResponse("/")
    
    consult = session.get(Consultation, consult_id)
    if not consult:
        return render_template("dashboard_patient", {
            "request": request,
            "user": user,
            "active_consultation": None,
            "logs": [],
            "error": "Consultation not found."
        })
    
    if consult.patient_id != user.id:
        return RedirectResponse("/dashboard", status_code=303)
    
    doctor = session.get(User, consult.doctor_id)
    if not doctor:
        return render_template("dashboard_patient", {
            "request": request,
            "user": user,
            "active_consultation": consult,
            "logs": [],
            "error": "Doctor information not found."
        })
    
    return render_template("billing", {
        "request": request,
        "user": user,
        "consultation": consult,
        "doctor_name": doctor.full_name
    })

@router.post("/billing/process")
async def process_payment(
    request: Request,
    consultation_id: int = Form(...),
    outcome: str = Form(...),
    session: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse("/")
    
    try:
        user = await get_current_user_from_token(token, session)
    except Exception:
        return RedirectResponse("/")
    
    consult = session.get(Consultation, consultation_id)
    if not consult:
        return JSONResponse(
            status_code=404,
            content={"error": "Consultation not found"}
        ) if request.headers.get("accept") == "application/json" else RedirectResponse("/dashboard")
    
    doctor = session.get(User, consult.doctor_id)
    if not doctor:
        return JSONResponse(
            status_code=404,
            content={"error": "Doctor not found"}
        ) if request.headers.get("accept") == "application/json" else RedirectResponse("/dashboard")
    
    if outcome == "success":
        consult.status = ConsultationStatus.ACTIVE
        consult.started_at = datetime.utcnow()
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
    if not token:
        return RedirectResponse("/")
    
    try:
        user = await get_current_user_from_token(token, session)
    except Exception:
        return RedirectResponse("/")
    
    consult = session.get(Consultation, consult_id)
    if not consult:
        return RedirectResponse("/dashboard")
    
    if user.id not in [consult.patient_id, consult.doctor_id]: 
        return HTMLResponse("Unauthorized Access", status_code=403)
    if consult.status != ConsultationStatus.ACTIVE: 
        return RedirectResponse("/dashboard")
    
    # Decrypt symptoms with error handling
    symptoms = decrypt_phi(consult.symptoms_enc) if consult.symptoms_enc else ""
    if not symptoms:
        symptoms = "Unable to decrypt symptoms data."
    
    # Fetch History (Previous Consultations) - ONLY for doctors
    history = []
    if user.role == UserRole.DOCTOR:
        prev_consults = session.exec(select(Consultation).where(
            Consultation.patient_id == consult.patient_id,
            Consultation.id != consult.id,
            Consultation.status == ConsultationStatus.COMPLETED
        ).order_by(Consultation.created_at.desc())).all()
        
        for pc in prev_consults:
            doc = session.get(User, pc.doctor_id)
            patient = session.get(User, pc.patient_id)
            
            # Decrypt with better error handling (decrypt_phi now returns empty string on error)
            symptoms_dec = decrypt_phi(pc.symptoms_enc) if pc.symptoms_enc else ""
            notes_dec = decrypt_phi(pc.notes_enc) if pc.notes_enc else ""
            transcript_dec = decrypt_phi(pc.transcript_enc) if pc.transcript_enc else None
            
            # If decryption failed (empty string), show user-friendly message
            # This can happen if encryption key changed or data is corrupted
            if not symptoms_dec:
                symptoms_dec = "Unable to decrypt symptoms data."
            if not notes_dec:
                notes_dec = "Unable to decrypt clinical notes."
            if not transcript_dec:
                transcript_dec = None
            
            # Parse prescriptions and files from notes
            prescriptions = []
            files = []
            clinical_notes = notes_dec
            
            if notes_dec and "Prescriptions:" in notes_dec:
                parts = notes_dec.split("Prescriptions:")
                clinical_notes = parts[0].strip()
                prescription_text = parts[1] if len(parts) > 1 else ""
                # Parse prescription lines
                lines = prescription_text.split('\n')
                for line in lines:
                    line = line.strip()
                    if line and (line[0].isdigit() or line.startswith('-')):
                        # Remove numbering
                        if line[0].isdigit() and '. ' in line:
                            line = line.split('. ', 1)[1]
                        elif line.startswith('- '):
                            line = line[2:]
                        prescriptions.append(line)
            
            # For files, assume they are listed in notes as "Files:" or similar
            if notes_dec and "Files:" in notes_dec:
                parts = clinical_notes.split("Files:")
                clinical_notes = parts[0].strip()
                file_text = parts[1] if len(parts) > 1 else ""
                lines = file_text.split('\n')
                for line in lines:
                    line = line.strip()
                    if line and (line[0].isdigit() or line.startswith('-')):
                        if line[0].isdigit() and '. ' in line:
                            line = line.split('. ', 1)[1]
                        elif line.startswith('- '):
                            line = line[2:]
                        files.append(line)
            
            history.append({
                "id": pc.id,
                "date": pc.created_at.strftime("%Y-%m-%d %H:%M"),
                "doctor": doc.full_name if doc else "Unknown Doctor",
                "doctor_specialty": doc.specialty if doc else "Unknown",
                "patient": patient.full_name if patient else "Unknown Patient",
                "specialty": pc.specialty,
                "symptoms": symptoms_dec if symptoms_dec else "No symptoms recorded.",
                "notes": clinical_notes if clinical_notes else "No clinical notes recorded.",
                "prescriptions": prescriptions,
                "files": files,
                "transcript": transcript_dec
            })
    
    # Get current doctor and patient info
    current_doctor = session.get(User, consult.doctor_id)
    current_patient = session.get(User, consult.patient_id)
    
    # Calculate session start timestamp for timer
    session_start = consult.started_at if consult.started_at else consult.created_at
    session_start_timestamp = int(session_start.timestamp() * 1000) if session_start else None

    audit_log(session, user, "Entered Secure Room", "Video Stream", "Consultation", consult.id)
    return render_template("consultation", {
        "request": request, 
        "user": user, 
        "consultation": consult, 
        "symptoms_decrypted": symptoms,
        "history": history,
        "current_doctor": current_doctor,
        "current_patient": current_patient,
        "session_start_timestamp": session_start_timestamp
    })

@router.post("/consultation/notes")
async def save_notes(request: Request, consultation_id: int = Form(...), notes: str = Form(...), session: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse("/")
    
    try:
        user = await get_current_user_from_token(token, session)
    except Exception:
        return RedirectResponse("/")
    
    consult = session.get(Consultation, consultation_id)
    if not consult:
        return RedirectResponse("/dashboard")
    
    if user.role != UserRole.DOCTOR:
        return HTMLResponse("Only doctors can save notes", status_code=403)
    
    if user.id != consult.doctor_id:
        return HTMLResponse("Unauthorized: You are not the assigned doctor", status_code=403)
    
    consult.notes_enc = encrypt_phi(notes)
    session.add(consult)
    session.commit()
    audit_log(session, user, "Appended Clinical Notes", "Medical Record", "Documentation", consult.id)
    return RedirectResponse(f"/consultation/{consultation_id}", status_code=303)

# --- Transfer Consultation ---
@router.get("/consultation/{consult_id}/available-doctors", response_class=JSONResponse)
async def get_available_doctors(request: Request, consult_id: int, session: Session = Depends(get_db)):
    """Get list of available doctors for transfer"""
    token = request.cookies.get("access_token")
    if not token:
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    
    try:
        user = await get_current_user_from_token(token, session)
    except Exception:
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
    
    consult = session.get(Consultation, consult_id)
    if not consult:
        return JSONResponse(status_code=404, content={"error": "Consultation not found"})
    
    # Only current doctor can see available doctors for transfer
    if user.id != consult.doctor_id or user.role != UserRole.DOCTOR:
        return JSONResponse(status_code=403, content={"error": "Only the assigned doctor can transfer"})
    
    # Get all doctors except the current one
    all_doctors = session.exec(select(User).where(
        User.role == UserRole.DOCTOR,
        User.id != consult.doctor_id
    )).all()
    
    # Debug: Log all doctors found
    print(f"DEBUG: Found {len(all_doctors)} doctors (excluding current doctor {consult.doctor_id})")
    
    # Filter to show only ONLINE doctors (exclude BUSY/OFFLINE/None)
    available_doctors = []
    for doc in all_doctors:
        # Handle None status
        if doc.status is None:
            print(f"DEBUG: Doctor {doc.id} ({doc.full_name}) has None status, excluding")
            continue
            
        # Handle both enum and string status
        if hasattr(doc.status, 'value'):
            status_value = doc.status.value
        elif isinstance(doc.status, str):
            status_value = doc.status
        else:
            status_value = str(doc.status)
        
        status_lower = status_value.lower() if isinstance(status_value, str) else str(status_value).lower()
        
        print(f"DEBUG: Doctor {doc.id} ({doc.full_name}) has status: {status_value} (lower: {status_lower})")
        
        # Include ONLINE doctors only
        if status_lower == 'online':
            available_doctors.append(doc)
            print(f"DEBUG: Doctor {doc.id} ({doc.full_name}) added to available list")
        else:
            print(f"DEBUG: Doctor {doc.id} ({doc.full_name}) excluded (status: {status_lower})")
    
    doctors_list = [
        {
            "id": doc.id,
            "name": doc.full_name,
            "specialty": doc.specialty or "General",
            "status": (doc.status.value if hasattr(doc.status, 'value') else str(doc.status)) if doc.status else "offline"
        }
        for doc in available_doctors
    ]
    
    print(f"DEBUG: Returning {len(doctors_list)} available doctors")
    
    return JSONResponse(content={"doctors": doctors_list})

@router.post("/consultation/transfer")
async def transfer_consultation(
    request: Request,
    consultation_id: int = Form(...),
    new_doctor_id: int = Form(...),
    reason: str = Form(None),
    session: Session = Depends(get_db)
):
    """Transfer consultation to another doctor"""
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse("/")
    
    try:
        user = await get_current_user_from_token(token, session)
    except Exception:
        return RedirectResponse("/")
    
    consult = session.get(Consultation, consultation_id)
    if not consult:
        if request.headers.get("accept") == "application/json":
            return JSONResponse(status_code=404, content={"error": "Consultation not found"})
        return RedirectResponse("/dashboard")
    
    # Only the current doctor can transfer
    if user.id != consult.doctor_id or user.role != UserRole.DOCTOR:
        if request.headers.get("accept") == "application/json":
            return JSONResponse(status_code=403, content={"error": "Only the assigned doctor can transfer"})
        return HTMLResponse("Unauthorized", status_code=403)
    
    # Check if consultation is active
    if consult.status != ConsultationStatus.ACTIVE:
        if request.headers.get("accept") == "application/json":
            return JSONResponse(status_code=400, content={"error": "Can only transfer active consultations"})
        return RedirectResponse(f"/consultation/{consultation_id}")
    
    # Get new doctor
    new_doctor = session.get(User, new_doctor_id)
    if not new_doctor or new_doctor.role != UserRole.DOCTOR:
        if request.headers.get("accept") == "application/json":
            return JSONResponse(status_code=404, content={"error": "Doctor not found"})
        return RedirectResponse(f"/consultation/{consultation_id}")
    
    # Check if new doctor is available (must be ONLINE)
    doctor_status = new_doctor.status
    if isinstance(doctor_status, str):
        try:
            doctor_status = DoctorStatus(doctor_status.lower())
        except ValueError:
            pass
    
    status_value = doctor_status.value if hasattr(doctor_status, 'value') else str(doctor_status)
    status_lower = status_value.lower() if isinstance(status_value, str) else str(status_value).lower()
    
    # Allow transfer to ONLINE doctors only
    if status_lower != 'online':
        error_msg = f"Selected doctor ({new_doctor.full_name}) is not available. Current status: {status_value}"
        if request.headers.get("accept") == "application/json":
            return JSONResponse(status_code=400, content={"error": error_msg})
        return RedirectResponse(f"/consultation/{consultation_id}")
    
    # Get old doctor
    old_doctor = session.get(User, consult.doctor_id)
    
    # Transfer consultation
    old_doctor_id = consult.doctor_id
    consult.doctor_id = new_doctor_id
    consult.updated_at = datetime.utcnow()
    
    # Update doctor statuses
    # Old doctor becomes available again
    old_doctor.status = DoctorStatus.ONLINE
    # New doctor becomes busy (even if they were offline, they're now taking the consultation)
    new_doctor.status = DoctorStatus.BUSY
    
    session.add(consult)
    session.add(old_doctor)
    session.add(new_doctor)
    session.commit()
    
    # Audit log
    transfer_reason = reason or "Emergency transfer"
    audit_log(session, user, f"Transferred Patient", f"From Dr. {old_doctor.full_name} to Dr. {new_doctor.full_name}", f"Transfer: {transfer_reason}", consult.id)
    audit_log(session, new_doctor, "Received Patient Transfer", f"Patient consultation #{consultation_id}", "Patient Care", consult.id)
    
    if request.headers.get("accept") == "application/json":
        return JSONResponse(content={
            "success": True,
            "message": f"Patient transferred to Dr. {new_doctor.full_name}",
            "new_consultation_url": f"/consultation/{consultation_id}"
        })
    
    return RedirectResponse(f"/consultation/{consultation_id}", status_code=303)

@router.get("/consultation/end/{consult_id}")
async def end_consultation(request: Request, consult_id: int, session: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse("/")
    
    try:
        user = await get_current_user_from_token(token, session)
    except Exception:
        return RedirectResponse("/")
    
    consult = session.get(Consultation, consult_id)
    if not consult:
        return RedirectResponse("/dashboard")
    
    # Only doctor or patient can end their own consultation
    if user.id not in [consult.patient_id, consult.doctor_id]:
        return HTMLResponse("Unauthorized Access", status_code=403)
    
    doctor = session.get(User, consult.doctor_id)
    if doctor:
        consult.status = ConsultationStatus.COMPLETED
        consult.ended_at = datetime.utcnow()
        doctor.status = DoctorStatus.ONLINE
        session.add(consult)
        session.add(doctor)
        session.commit()
        audit_log(session, user, "Ended Consultation", f"Consultation #{consult_id}", "Session Management", consult_id)
    
    return RedirectResponse("/dashboard", status_code=303)

@router.get("/doctor/toggle_status")
async def toggle_status(request: Request, session: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    user = await get_current_user_from_token(token, session)
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
    """WebSocket endpoint for chat, signaling, and live transcript."""
    await manager.connect(websocket, consult_id)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg_json = json.loads(data)
                msg_type = msg_json.get("type")

                # WebRTC signaling should not echo back to sender
                if msg_type in {"offer", "answer", "candidate"}:
                    await manager.broadcast_except(data, consult_id, websocket)
                    continue

                # Structured chat message
                if msg_type == "chat":
                    # Ensure sender metadata is present
                    msg_json.setdefault("user_id", user_id)
                    msg_json.setdefault("timestamp", datetime.utcnow().isoformat())
                    await manager.broadcast(json.dumps(msg_json), consult_id)
                    continue

                # Unknown structured message – broadcast as-is
                await manager.broadcast(data, consult_id)

            except json.JSONDecodeError:
                # Plain text fallback -> wrap into chat payload
                chat_payload = json.dumps({
                    "type": "chat",
                    "user_id": user_id,
                    "text": data,
                    "timestamp": datetime.utcnow().isoformat()
                })
                await manager.broadcast(chat_payload, consult_id)
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