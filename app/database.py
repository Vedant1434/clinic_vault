from sqlmodel import SQLModel, Session, create_engine
from app.config import settings

# Import models to ensure they're registered with SQLModel
from app.models import User, Consultation, PrivacyLog  # noqa: F401

# check_same_thread=False is needed only for SQLite
engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})

def get_db():
    with Session(engine) as session:
        yield session

def init_db():
    """Initialize database and create all tables"""
    SQLModel.metadata.create_all(engine)