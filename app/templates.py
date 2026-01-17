from fastapi.responses import HTMLResponse
from jinja2 import Environment, DictLoader

# Storing templates in a dictionary for portability
HTML_TEMPLATES = {
    "base": """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ClinicVault | Enterprise Health System</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            :root { --primary: #0d6efd; --secure: #198754; --admin: #6610f2; --bg: #f8f9fa; }
            body { background-color: var(--bg); font-family: 'Segoe UI', system-ui, sans-serif; }
            .navbar { background: white; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
            .secure-badge { background: #e8f5e9; color: #1b5e20; padding: 4px 8px; border-radius: 4px; font-size: 0.8em; border: 1px solid #c8e6c9; }
            .admin-badge { background: #f3e5f5; color: #4a148c; padding: 4px 8px; border-radius: 4px; font-size: 0.8em; border: 1px solid #e1bee7; }
            .timeline-item { border-left: 2px solid #dee2e6; padding-left: 20px; padding-bottom: 20px; position: relative; }
            .timeline-item::before { content: ''; position: absolute; left: -6px; top: 0; width: 10px; height: 10px; border-radius: 50%; background: var(--primary); }
            .timeline-date { font-size: 0.85em; color: #6c757d; }
            .card { border: none; box-shadow: 0 2px 8px rgba(0,0,0,0.05); border-radius: 8px; }
            
            /* Video Chat Styles */
            .video-container { position: relative; width: 100%; height: 400px; background: #000; border-radius: 8px; overflow: hidden; }
            video { width: 100%; height: 100%; object-fit: cover; }
            #localVideo { position: absolute; bottom: 20px; right: 20px; width: 120px; height: 90px; border: 2px solid white; border-radius: 4px; z-index: 10; }
            
            /* Transcript Overlay */
            #transcriptOverlay {
                position: absolute;
                bottom: 80px; /* Moved up slightly */
                left: 50%;
                transform: translateX(-50%);
                width: 80%;
                text-align: center;
                color: #fff;
                background: rgba(0, 0, 0, 0.7);
                padding: 12px;
                border-radius: 20px;
                font-size: 1.2em;
                font-weight: 500;
                display: none;
                z-index: 20;
                pointer-events: none;
                transition: opacity 0.3s ease-in-out;
                text-shadow: 0 1px 2px rgba(0,0,0,0.8);
            }
            .transcript-badge { font-size: 0.75em; background: #e3f2fd; color: #0d47a1; padding: 2px 6px; border-radius: 4px; margin-right: 5px; }
        </style>
    </head>
    <body>
        <nav class="navbar navbar-expand-lg navbar-light mb-4">
            <div class="container">
                <a class="navbar-brand fw-bold" href="/">
                    <i class="fas fa-hospital-user text-primary"></i> ClinicVault <small class="text-muted fw-light">Enterprise</small>
                </a>
                <div class="d-flex align-items-center">
                    {% if user %}
                        <span class="me-3 text-muted">
                            {{ user.full_name }} 
                            {% if user.role == 'admin' %}
                                <span class="badge bg-primary">SUPERVISOR</span>
                            {% elif user.role == 'doctor' %}
                                <span class="badge bg-success">DOCTOR</span>
                            {% endif %}
                        </span>
                        <a href="/logout" class="btn btn-outline-secondary btn-sm">Logout</a>
                    {% endif %}
                </div>
            </div>
        </nav>
        <div class="container">
            {% block content %}{% endblock %}
        </div>
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    """,
    "login": """{% extends "base" %}
    {% block content %}
    <div class="row justify-content-center mt-5">
        <div class="col-md-5">
            <div class="card p-4">
                <h3 class="text-center mb-4">Hospital Portal</h3>
                <form action="/auth/login" method="post">
                    <div class="mb-3"><label>Email Address</label><input type="email" name="username" class="form-control" required></div>
                    <div class="mb-3"><label>Password</label><input type="password" name="password" class="form-control" required></div>
                    <button type="submit" class="btn btn-primary w-100 mb-2">Secure Login</button>
                </form>
                <div class="text-center mt-3"><a href="/register" class="text-decoration-none">New Patient? Register Here</a></div>
                <hr>
                <div class="d-grid gap-2"><form action="/auth/seed" method="post"><button class="btn btn-outline-secondary btn-sm w-100">Initialize Demo Data</button></form></div>
            </div>
        </div>
    </div>
    {% endblock %}""",
    "register": """{% extends "base" %}
    {% block content %}
    <div class="row justify-content-center mt-5">
        <div class="col-md-5">
            <div class="card p-4">
                <h3 class="text-center mb-4">Patient Registration</h3>
                <form action="/auth/register" method="post">
                    <div class="mb-3"><label>Full Name</label><input type="text" name="full_name" class="form-control" required></div>
                    <div class="mb-3"><label>Email Address</label><input type="email" name="email" class="form-control" required></div>
                    <div class="mb-3"><label>Password</label><input type="password" name="password" class="form-control" required></div>
                    <button type="submit" class="btn btn-success w-100 mb-2">Create Record</button>
                </form>
                <div class="text-center mt-3"><a href="/" class="text-decoration-none">Already have an account? Login</a></div>
            </div>
        </div>
    </div>
    {% endblock %}""",
    "dashboard_admin": """{% extends "base" %}
    {% block content %}
    <div class="row">
        <div class="col-md-12 mb-4">
            <div class="card border-primary">
                <div class="card-header bg-primary text-white d-flex justify-content-between"><h5 class="mb-0">Supervisor Dashboard</h5><span><i class="fas fa-user-shield"></i> Admin Access</span></div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-4">
                            <h6>Add New Doctor</h6>
                            <form action="/admin/add_doctor" method="post" class="border p-3 rounded bg-light">
                                <div class="mb-2"><input type="text" name="full_name" class="form-control form-control-sm" placeholder="Dr. Name" required></div>
                                <div class="mb-2"><input type="email" name="email" class="form-control form-control-sm" placeholder="Email" required></div>
                                <div class="mb-2"><input type="password" name="password" class="form-control form-control-sm" placeholder="Password" required></div>
                                <div class="mb-2"><select name="specialty" class="form-select form-select-sm"><option value="Cardiology">Cardiology</option><option value="Dermatology">Dermatology</option><option value="General">General Practice</option></select></div>
                                <button class="btn btn-primary btn-sm w-100">Onboard Doctor</button>
                            </form>
                        </div>
                        <div class="col-md-8">
                            <h6>Medical Staff Status</h6>
                            <table class="table table-sm table-hover">
                                <thead><tr><th>Name</th><th>Specialty</th><th>Status</th></tr></thead>
                                <tbody>{% for doc in doctors %}<tr><td>{{ doc.full_name }}</td><td>{{ doc.specialty }}</td><td><span class="badge {% if doc.status == 'online' %}bg-success{% elif doc.status == 'busy' %}bg-danger{% else %}bg-secondary{% endif %}">{{ doc.status | upper }}</span></td></tr>{% endfor %}</tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <div class="col-md-12">
            <div class="card">
                <div class="card-header bg-white"><h5 class="mb-0"><i class="fas fa-history"></i> System-Wide Privacy Log</h5></div>
                <div class="card-body" style="max-height: 400px; overflow-y: auto;">
                    <table class="table table-striped table-sm text-small">
                        <thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Target</th><th>Purpose</th></tr></thead>
                        <tbody>{% for log in logs %}<tr><td>{{ log.timestamp.strftime('%Y-%m-%d %H:%M:%S') }}</td><td>{{ log.actor_name }}</td><td>{{ log.action }}</td><td>{{ log.target_data }}</td><td>{{ log.purpose }}</td></tr>{% endfor %}</tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
    {% endblock %}""",
    "dashboard_patient": """{% extends "base" %}
    {% block content %}
    <div class="row">
        <div class="col-md-8">
            <div class="card mb-4">
                <div class="card-header bg-white d-flex justify-content-between"><h5 class="mb-0">Patient Triage</h5><span class="secure-badge"><i class="fas fa-shield-alt"></i> HIPAA Compliant</span></div>
                <div class="card-body">
                    {% if active_consultation %}
                        <div class="alert alert-info">
                            <h5><i class="fas fa-user-md"></i> Consultation #{{ active_consultation.id }}</h5>
                            <p><strong>Status:</strong> {{ active_consultation.status | upper }}</p>
                            <p><strong>Specialty:</strong> {{ active_consultation.specialty }}</p>
                            {% if active_consultation.status == 'pending_payment' %}<a href="/billing/{{ active_consultation.id }}" class="btn btn-warning w-100">Proceed to Billing Counter</a>{% elif active_consultation.status == 'active' %}<a href="/consultation/{{ active_consultation.id }}" class="btn btn-success w-100">Enter Consultation Room</a>{% endif %}
                        </div>
                    {% else %}
                        <h6>Start New Triage</h6>
                        <form action="/triage/start" method="post">
                            <div class="mb-3"><label>Select Required Specialty</label><select name="specialty" class="form-select"><option value="General">General Practice</option><option value="Cardiology">Cardiology</option><option value="Dermatology">Dermatology</option></select></div>
                            <div class="mb-3"><label>Describe Symptoms</label><textarea name="symptoms" class="form-control" rows="3" required></textarea><small class="text-muted"><i class="fas fa-lock"></i> Encrypted at rest.</small></div>
                            <button class="btn btn-primary">Find Available Doctor</button>
                        </form>
                    {% endif %}
                </div>
            </div>
        </div>
        <div class="col-md-4">
            <div class="card">
                <div class="card-header bg-white"><h5 class="mb-0"><i class="fas fa-history"></i> My Privacy Timeline</h5></div>
                <div class="card-body" style="max-height: 500px; overflow-y: auto;">
                    {% for log in logs %}<div class="timeline-item"><div class="timeline-date">{{ log.timestamp.strftime('%H:%M:%S') }}</div><strong>{{ log.actor_name }}</strong><div>{{ log.action }}</div><div class="small text-muted">Target: {{ log.target_data }}</div><div class="small text-info fst-italic">Purpose: {{ log.purpose }}</div></div>{% endfor %}
                </div>
            </div>
        </div>
    </div>
    {% endblock %}""",
    "dashboard_doctor": """{% extends "base" %}
    {% block content %}
    <div class="row">
        <div class="col-md-12 mb-4"><div class="card"><div class="card-body d-flex justify-content-between align-items-center"><div><h4 class="mb-0">Dr. {{ user.full_name }}</h4><span class="badge bg-secondary">{{ user.specialty }}</span></div><div><span class="me-2">Current Status: <strong class="{% if user.status == 'online' %}text-success{% elif user.status == 'busy' %}text-danger{% else %}text-muted{% endif %}">{{ user.status | upper }}</strong></span><a href="/doctor/toggle_status" class="btn btn-outline-primary btn-sm">Toggle Online/Offline</a></div></div></div></div>
    </div>
    <h4>Assigned Patients</h4>
    <div class="row">
        {% for consult in consultations %}<div class="col-md-6"><div class="card mb-3"><div class="card-body"><h5 class="card-title">Patient #{{ consult.patient_id }}</h5><p class="card-text">Status: <strong>{{ consult.status }}</strong></p>{% if consult.status == 'active' %}<a href="/consultation/{{ consult.id }}" class="btn btn-success">Enter Consultation Room</a>{% else %}<span class="text-muted">Waiting for Payment/Triage</span>{% endif %}</div></div></div>{% else %}<div class="col-12"><p class="text-muted">No active assignments. Go 'Online' to receive patients.</p></div>{% endfor %}
    </div>
    {% endblock %}""",
    "billing": """{% extends "base" %}
    {% block content %}
    <div class="row justify-content-center"><div class="col-md-6"><div class="card border-warning"><div class="card-header bg-warning text-dark"><h5 class="mb-0"><i class="fas fa-file-invoice-dollar"></i> Hospital Billing Counter</h5></div><div class="card-body text-center"><h3>Amount Due: ₹500.00</h3><p class="text-muted">Consultation ID: #{{ consultation.id }}</p><p>Doctor Assigned: <strong>{{ doctor_name }}</strong></p><hr><div class="d-flex gap-2 justify-content-center"><form action="/billing/process" method="post"><input type="hidden" name="consultation_id" value="{{ consultation.id }}"><input type="hidden" name="outcome" value="success"><button class="btn btn-success btn-lg">Simulate Success</button></form><form action="/billing/process" method="post"><input type="hidden" name="consultation_id" value="{{ consultation.id }}"><input type="hidden" name="outcome" value="fail"><button class="btn btn-danger btn-lg">Simulate Failure</button></form></div></div></div></div></div>
    {% endblock %}""",
    "consultation": """{% extends "base" %}
    {% block content %}
    <div class="row">
        <div class="col-md-8">
            <!-- WebRTC Video Container -->
            <div class="card mb-3 bg-dark text-white video-container">
                <video id="remoteVideo" autoplay playsinline></video>
                <video id="localVideo" autoplay playsinline muted></video>
                <div id="transcriptOverlay"></div> <!-- Transcript Overlay -->
                
                <div class="position-absolute bottom-0 start-0 p-3" style="width: 100%; z-index: 30;">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <span class="badge bg-danger animate-pulse"><i class="fas fa-circle"></i> Encrypted Live Feed</span>
                            <button id="startCallBtn" class="btn btn-success btn-sm ms-2">Start Video Call</button>
                        </div>
                        <button id="recordBtn" class="btn btn-outline-light btn-sm"><i class="fas fa-microphone"></i> Start Transcription</button>
                    </div>
                </div>
            </div>
            
            {% if user.role == 'doctor' %}
            <div class="card">
                <div class="card-header d-flex justify-content-between">
                    <span>Medical Notes (Encrypted Storage)</span>
                </div>
                <div class="card-body">
                    <form action="/consultation/notes" method="post">
                        <input type="hidden" name="consultation_id" value="{{ consultation.id }}">
                        <textarea name="notes" class="form-control mb-2" rows="4" placeholder="Type clinical notes here..."></textarea>
                        <button class="btn btn-primary btn-sm">Save & Encrypt</button>
                    </form>
                    <hr>
                    <a href="/consultation/end/{{ consultation.id }}" class="btn btn-outline-danger w-100">End Session</a>
                </div>
            </div>
            {% else %}
            <!-- Patient View: Just Leave Button -->
            <div class="card">
                 <div class="card-body">
                    <p class="text-muted">You are in a secure session with your doctor.</p>
                    <a href="/dashboard" class="btn btn-outline-secondary w-100">Leave Room</a>
                 </div>
            </div>
            {% endif %}
        </div>
        
        <div class="col-md-4">
            <!-- Patient Data -->
            <div class="card mb-3">
                <div class="card-header bg-info text-white">Current Patient Data</div>
                <div class="card-body">
                    <h6>Symptoms (Decrypted):</h6>
                    <p class="alert alert-secondary">{{ symptoms_decrypted }}</p>
                    <small class="text-muted d-block mb-2"><i class="fas fa-eye"></i> Decrypted for: {{ user.full_name }}</small>
                </div>
            </div>

            <!-- Chat & Transcript -->
            <div class="card mb-3" style="height: 300px;">
                <div class="card-header">Live Chat & Transcription</div>
                <div class="card-body bg-light" id="chat-box" style="overflow-y: auto;">
                    <div class="text-muted small text-center">System: Secure channel established.</div>
                </div>
                <div class="card-footer">
                    <input type="text" id="msg-input" class="form-control form-control-sm" placeholder="Type message...">
                </div>
            </div>

            <!-- History Sidebar (Doctor Only) -->
            {% if history %}
            <div class="card">
                <div class="card-header bg-secondary text-white">Patient History</div>
                <div class="card-body p-0" style="max-height: 200px; overflow-y: auto;">
                    <ul class="list-group list-group-flush">
                        {% for h in history %}
                        <li class="list-group-item">
                            <small class="fw-bold">{{ h.date }} - {{ h.specialty }}</small><br>
                            <small class="text-muted">Dr. {{ h.doctor }}</small>
                            <div class="mt-1 small fst-italic border-start border-primary ps-2">{{ h.notes }}</div>
                        </li>
                        {% endfor %}
                    </ul>
                </div>
            </div>
            {% endif %}
        </div>
    </div>

    <!-- WebRTC & Socket Logic -->
    <script>
        const consultId = "{{ consultation.id }}";
        const userId = "{{ user.id }}";
        const wsUrl = "ws://" + window.location.host + "/ws/" + consultId + "/" + userId;
        const ws = new WebSocket(wsUrl);
        
        const localVideo = document.getElementById('localVideo');
        const remoteVideo = document.getElementById('remoteVideo');
        const chatBox = document.getElementById('chat-box');
        const transcriptOverlay = document.getElementById('transcriptOverlay');
        let transcriptTimeout;

        // WebRTC Config
        const rtcConfig = { iceServers: [{ urls: "stun:stun.l.google.com:19302" }] };
        let peerConnection;
        let localStream;

        // --- WebSocket Handling ---
        ws.onmessage = async function(event) {
            try {
                const msg = JSON.parse(event.data);
                
                if (msg.type === "transcript") {
                    // Show in Video Overlay
                    transcriptOverlay.textContent = msg.text;
                    transcriptOverlay.style.display = 'block';
                    
                    // Show in Chat but styled differently
                    addMessage("Transcript", msg.text, "transcript-badge");
                    
                    // Clear overlay after 4 seconds
                    clearTimeout(transcriptTimeout);
                    transcriptTimeout = setTimeout(() => {
                        transcriptOverlay.style.display = 'none';
                    }, 4000);
                } 
                else if (msg.type === "offer") { await handleOffer(msg); } 
                else if (msg.type === "answer") { await handleAnswer(msg); } 
                else if (msg.type === "candidate") { await handleCandidate(msg); }
                else { addMessage("User", JSON.stringify(msg)); }
            } catch (e) {
                addMessage("", event.data);
            }
        };

        function addMessage(sender, text, badgeClass) {
            const div = document.createElement('div');
            div.className = 'mb-2 p-2 bg-white border rounded';
            if (badgeClass) {
                div.innerHTML = `<span class="${badgeClass}">${sender}</span> ${text}`;
            } else {
                div.textContent = text;
            }
            chatBox.appendChild(div);
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        // --- Chat ---
        document.getElementById('msg-input').onkeypress = function(e) {
            if(e.key === 'Enter'){
                ws.send(this.value);
                addMessage("Me", this.value);
                this.value = '';
            }
        };

        // --- WebRTC Logic ---
        async function startCall() {
            localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
            localVideo.srcObject = localStream;
            
            peerConnection = new RTCPeerConnection(rtcConfig);
            peerConnection.onicecandidate = e => {
                if(e.candidate) {
                    ws.send(JSON.stringify({ type: "candidate", candidate: e.candidate }));
                }
            };
            peerConnection.ontrack = e => {
                remoteVideo.srcObject = e.streams[0];
            };
            localStream.getTracks().forEach(track => peerConnection.addTrack(track, localStream));
            
            const offer = await peerConnection.createOffer();
            await peerConnection.setLocalDescription(offer);
            ws.send(JSON.stringify({ type: "offer", sdp: offer }));
            
            document.getElementById('startCallBtn').style.display = 'none';
        }

        async function handleOffer(msg) {
            if(!localStream) {
                localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
                localVideo.srcObject = localStream;
            }
            
            peerConnection = new RTCPeerConnection(rtcConfig);
            peerConnection.onicecandidate = e => {
                if(e.candidate) ws.send(JSON.stringify({ type: "candidate", candidate: e.candidate }));
            };
            peerConnection.ontrack = e => {
                remoteVideo.srcObject = e.streams[0];
            };
            localStream.getTracks().forEach(track => peerConnection.addTrack(track, localStream));
            
            await peerConnection.setRemoteDescription(new RTCSessionDescription(msg.sdp));
            const answer = await peerConnection.createAnswer();
            await peerConnection.setLocalDescription(answer);
            ws.send(JSON.stringify({ type: "answer", sdp: answer }));
        }

        async function handleAnswer(msg) {
            await peerConnection.setRemoteDescription(new RTCSessionDescription(msg.sdp));
        }

        async function handleCandidate(msg) {
            if(peerConnection) {
                await peerConnection.addIceCandidate(new RTCIceCandidate(msg.candidate));
            }
        }
        
        document.getElementById('startCallBtn').onclick = startCall;

        // --- ROBUST Audio Transcription Logic ---
        // Filter out tiny audio blobs to prevent backend processing errors
        
        let isRecording = false;
        let recorderStream = null;
        const recordBtn = document.getElementById('recordBtn');

        async function startAudioLoop() {
            if (!isRecording) return;
            
            if (!recorderStream) {
                 recorderStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            }

            const mediaRecorder = new MediaRecorder(recorderStream);
            const audioChunks = [];

            mediaRecorder.ondataavailable = event => {
                audioChunks.push(event.data);
            };

            mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                
                // IGNORE tiny blobs (less than 1KB) which are usually just empty headers
                if (audioBlob.size > 1024 && isRecording) {
                    const formData = new FormData();
                    formData.append("audio_blob", audioBlob);
                    formData.append("consultation_id", consultId);
                    formData.append("user_id", userId);
                    
                    fetch("/consultation/transcribe", { method: "POST", body: formData });
                }
                
                if (isRecording) {
                    startAudioLoop(); 
                }
            };

            mediaRecorder.start();
            
            setTimeout(() => {
                if (mediaRecorder.state === "recording") {
                    mediaRecorder.stop();
                }
            }, 3000); 
        }

        recordBtn.onclick = async () => {
            if (!isRecording) {
                isRecording = true;
                recordBtn.innerHTML = '<i class="fas fa-stop"></i> Stop Transcription';
                recordBtn.classList.replace('btn-outline-light', 'btn-danger');
                startAudioLoop();
            } else {
                isRecording = false;
                recordBtn.innerHTML = '<i class="fas fa-microphone"></i> Start Transcription';
                recordBtn.classList.replace('btn-danger', 'btn-outline-light');
            }
        };

    </script>
    {% endblock %}"""
}

def render_template(name: str, context: dict):
    env = Environment(loader=DictLoader(HTML_TEMPLATES))
    tmpl = env.get_template(name)
    return HTMLResponse(tmpl.render(**context))