from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from jose import JWTError, jwt
from cryptography.fernet import Fernet
from sqlmodel import Session, select

from app.config import settings
from app.database import get_db
from app.models import User, PrivacyLog, UserRole

# Encryption Suite
cipher_suite = Fernet(settings.ENCRYPTION_KEY)
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- Encryption Utils ---
def encrypt_phi(data: str) -> str:
    if not data: return ""
    return cipher_suite.encrypt(data.encode()).decode()

def decrypt_phi(token: str) -> str:
    if not token: 
        return ""
    
    # Check if token looks like valid encrypted data
    if len(token) < 10:  # Fernet tokens are typically much longer
        return ""
    
    try:
        decrypted = cipher_suite.decrypt(token.encode()).decode()
        # Return empty string if decryption results in corruption message
        if "[DATA CORRUPTION ERROR]" in decrypted:
            return ""
        return decrypted
    except Exception as e:
        # Log error with more context for debugging
        error_type = type(e).__name__
        error_msg = str(e) if str(e) else "Unknown error"
        # Only log if it's not a common "invalid token" error (which is expected for old data)
        if "InvalidToken" not in error_type and "InvalidSignature" not in error_type:
            print(f"Decryption error ({error_type}): {error_msg}")
        return ""

# --- Auth Utils ---
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

async def get_current_user_from_token(token: str, session: Session) -> User:
    """Helper function to get user from token string (for cookie-based auth)"""
    if not token:
        raise HTTPException(status_code=401, detail="Missing authentication token")

    if token.startswith("Bearer "):
        token = token[7:]
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

async def get_current_user(token: str = Depends(oauth2_scheme), session: Session = Depends(get_db)):
    """Dependency for OAuth2 token-based authentication"""
    return await get_current_user_from_token(token, session)

def audit_log(session: Session, actor: User, action: str, target: str, purpose: str, consult_id: Optional[int] = None):
    log = PrivacyLog(
        consultation_id=consult_id,
        actor_id=actor.id,
        actor_name=f"{actor.full_name} ({actor.role.value})",
        action=action,
        target_data=target,
        purpose=purpose
    )
    session.add(log)
    session.commit()