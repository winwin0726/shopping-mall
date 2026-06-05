from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from backend.config import settings

# DB URL은 설정(config)에서 단일 관리. 기본값은 프로젝트 루트 sql_app.db (SQLite).
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_PATH = os.path.join(_BASE_DIR, "sql_app.db")
SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL or f"sqlite:///{_DB_PATH}"

# SQLite 일 때만 check_same_thread=False 필요
_connect_args = (
    {"check_same_thread": False, "timeout": 30.0}
    if SQLALCHEMY_DATABASE_URL.startswith("sqlite")
    else {}
)
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
