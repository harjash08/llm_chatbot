from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import create_engine
from core.settings import settings

engine=create_engine(settings.DATABASE_URL)
Base=declarative_base()
SessionLocal=sessionmaker(
    bind=engine
)

def get_db():
    db=SessionLocal()
    try:
        yield db
    finally:
        db.close()