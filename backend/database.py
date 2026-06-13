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

# 서버형 데이터베이스(MySQL, PostgreSQL)용 커넥션 풀 튜닝 옵션
_pool_options = {}
if not SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    _pool_options = {
        "pool_size": 10,
        "max_overflow": 20,
        "pool_recycle": 3600,  # 1시간마다 커넥션 재생성 (DB 연결 끊김 방지)
        "pool_pre_ping": True  # 커넥션 사용 전 살아있는지 핑 확인
    }

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=_connect_args, **_pool_options)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
