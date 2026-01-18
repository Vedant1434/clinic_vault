import os
import secrets
from cryptography.fernet import Fernet

class Settings:
    def __init__(self):
        self.SECRET_KEY: str = secrets.token_hex(32)
        self.ALGORITHM: str = "HS256"
        self.ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
        self.DATABASE_URL: str = "sqlite:///./clinicvault.db"
        
        # Persistent encryption key - load from file or generate and save
        encryption_key_file = ".encryption_key"
        if os.path.exists(encryption_key_file):
            # Load existing key
            with open(encryption_key_file, 'rb') as f:
                self.ENCRYPTION_KEY: bytes = f.read()
        else:
            # Generate new key and save it
            self.ENCRYPTION_KEY: bytes = Fernet.generate_key()
            with open(encryption_key_file, 'wb') as f:
                f.write(self.ENCRYPTION_KEY)

settings = Settings()