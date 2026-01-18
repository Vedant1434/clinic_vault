# ClinicVault Enterprise

## Overview

ClinicVault Enterprise is a comprehensive, HIPAA-compliant telemedicine platform designed for secure video consultations between patients and healthcare providers. Built with FastAPI and modern web technologies, it provides real-time video calling, automated transcription, encrypted patient data storage, and comprehensive audit logging.

## Key Features

### 🔒 Security & Compliance
- **End-to-End Encryption**: All patient health information (PHI) is encrypted using AES-256 encryption
- **JWT Authentication**: Secure token-based authentication with role-based access control
- **Audit Logging**: Comprehensive logging of all system activities for compliance and security monitoring
- **HIPAA Compliance**: Designed to meet healthcare data protection standards

### 📹 Real-Time Communication
- **WebRTC Video Calls**: High-quality, encrypted video consultations
- **WebSocket Integration**: Real-time messaging and status updates
- **Live Transcription**: Automatic speech-to-text transcription during consultations
- **Video Overlay**: Transcripts can be displayed directly on the video feed

### 👥 User Management
- **Role-Based Access**: Separate interfaces for Patients, Doctors, and Administrators
- **Doctor Availability**: Real-time status tracking (Online/Offline/Busy)
- **Patient History**: Encrypted storage and retrieval of consultation records

### 📋 Clinical Workflow
- **Electronic Notes**: Secure clinical note-taking with templates
- **Vital Signs Tracking**: Integrated vital signs recording and storage
- **Prescription Management**: Digital prescription creation and management
- **File Sharing**: Secure document upload and sharing during consultations

### 🛠️ Technical Features
- **Asynchronous Processing**: Built with async/await for high performance
- **Database Integration**: SQLModel with SQLite/PostgreSQL support
- **RESTful API**: Comprehensive API for integrations
- **Responsive UI**: Bootstrap-based responsive web interface

## Architecture

### Backend Architecture
```
clinic_vault/
├── app/
│   ├── main.py              # FastAPI application entry point
│   ├── config.py            # Application configuration and settings
│   ├── database.py          # Database connection and initialization
│   ├── models.py            # SQLModel database models
│   ├── security.py          # Authentication, encryption, and security utilities
│   ├── transcription.py     # Audio transcription processing
│   ├── templates.py         # Jinja2 template rendering utilities
│   └── routers/
│       ├── __init__.py
│       ├── auth.py          # Authentication endpoints (login/register)
│       ├── admin.py         # Administrative functions
│       └── workflow.py      # Main consultation workflow
├── tests/
│   ├── __init__.py
│   ├── test_auth.py         # Authentication tests
│   ├── test_security.py     # Security function tests
│   └── test_workflow.py     # Workflow and API tests
├── requirements.txt         # Python dependencies
├── pytest.ini              # Test configuration
└── README.md               # This file
```

### Data Flow
1. **Authentication**: Users authenticate via JWT tokens
2. **Consultation Setup**: Patients request consultations, doctors accept
3. **Real-Time Session**: WebRTC handles video, WebSockets manage real-time data
4. **Transcription**: Audio chunks are processed and transcribed in real-time
5. **Data Storage**: All PHI is encrypted before database storage
6. **Audit Logging**: All actions are logged for compliance

### Security Architecture
- **Encryption at Rest**: PHI fields encrypted using Fernet (AES-256)
- **Encryption in Transit**: HTTPS required for all communications
- **Access Control**: Role-based permissions with database-level enforcement
- **Session Management**: Secure cookie-based sessions with CSRF protection

## Installation

### Prerequisites
- Python 3.8+
- pip package manager
- SQLite (default) or PostgreSQL (production)

### Setup
1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd clinic_vault
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize the database**:
   ```bash
   python -c "from app.database import init_db; init_db()"
   ```

## Usage

### Development Server
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Access the application at `http://localhost:8000`

### Production Deployment
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### API Documentation
When running, visit `http://localhost:8000/docs` for interactive API documentation.

## API Endpoints

### Authentication
- `POST /auth/login` - User login
- `POST /auth/register` - User registration
- `POST /auth/logout` - User logout

### Dashboard
- `GET /dashboard` - User dashboard (role-specific)

### Consultations
- `GET /consultation/start/{patient_id}` - Start consultation
- `POST /consultation/notes` - Save clinical notes
- `POST /consultation/transcribe` - Process audio transcription
- `GET /consultation/end/{consultation_id}` - End consultation

### WebSocket
- `WS /ws/{consultation_id}/{user_id}` - Real-time communication

### Administration
- `GET /admin/users` - User management
- `GET /admin/logs` - Audit logs
- `POST /admin/assign-doctor` - Assign doctors to consultations

## Testing

### Run All Tests
```bash
pytest
```

### Run Specific Test File
```bash
pytest tests/test_auth.py
pytest tests/test_workflow.py
pytest tests/test_security.py
```

### Test Configuration
- Tests use pytest with asyncio support
- Database tests use in-memory SQLite
- Coverage reporting available with `pytest --cov=app`

## Configuration

### Environment Variables
- `DATABASE_URL`: Database connection string (default: SQLite)
- `SECRET_KEY`: JWT secret key (auto-generated if not set)
- `ENCRYPTION_KEY`: AES encryption key (auto-generated and persisted)

### Settings
Edit `app/config.py` to customize:
- Token expiration times
- Database settings
- Security parameters

## Deployment

### Docker Deployment
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN python -c "from app.database import init_db; init_db()"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Production Considerations
- Use PostgreSQL for production database
- Configure HTTPS with SSL certificates
- Set up proper logging and monitoring
- Implement backup strategies for encrypted data
- Configure firewall and security groups
- Set up load balancing for high availability

## Security Best Practices

### Data Protection
- All PHI is encrypted before storage
- Encryption keys are securely managed and rotated
- Database backups include encryption keys separately

### Access Control
- Multi-factor authentication recommended
- Regular password rotation policies
- Session timeout configurations

### Network Security
- HTTPS required for all connections
- WebRTC connections use DTLS encryption
- WebSocket connections authenticated

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines
- Follow PEP 8 style guidelines
- Write comprehensive tests for new features
- Update documentation for API changes
- Ensure all tests pass before submitting PR

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Create an issue in the GitHub repository
- Contact the development team
- Check the documentation for common solutions

## Changelog

### Version 1.0.0
- Initial release with core telemedicine features
- WebRTC video calling
- Real-time transcription
- Encrypted PHI storage
- Role-based access control
- Comprehensive audit logging

---

**ClinicVault Enterprise** - Secure, compliant telemedicine for modern healthcare.</content>