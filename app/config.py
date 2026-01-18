import os
import secrets
from cryptography.fernet import Fernet

class Settings:
    def __init__(self):
        self.SECRET_KEY: str = os.getenv("SECRET_KEY", secrets.token_hex(32))
        self.ALGORITHM: str = "HS256"
        self.ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
        
        # Priority: Env Var > Local File > Default SQLite
        self.DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./clinicvault.db")
        
        # Priority: Env Var > Local File > Generate New
        env_key = os.getenv("ENCRYPTION_KEY")
        if env_key:
            self.ENCRYPTION_KEY = env_key.encode()
        else:
            # Fallback for local testing only
            encryption_key_file = ".encryption_key"
            if os.path.exists(encryption_key_file):
                with open(encryption_key_file, 'rb') as f:
                    self.ENCRYPTION_KEY = f.read()
            else:
                self.ENCRYPTION_KEY = Fernet.generate_key()
                with open(encryption_key_file, 'wb') as f:
                    f.write(self.ENCRYPTION_KEY)

settings = Settings()