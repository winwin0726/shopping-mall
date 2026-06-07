import os
from typing import Optional
from pydantic_settings import BaseSettings

# backend/.env 파일의 절대 경로 계산
base_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(base_dir, ".env")

# 기본 DB는 프로젝트 루트의 sql_app.db (SQLite). 환경변수 DATABASE_URL 로 PostgreSQL 등으로 교체 가능.
_default_sqlite = "sqlite:///" + os.path.join(os.path.dirname(base_dir), "sql_app.db")

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI E-Commerce Platform API"
    DATABASE_URL: str = _default_sqlite
    # JWT 설정(SECRET_KEY/ALGORITHM/만료)의 단일 소스는 backend/utils/security.py.
    # (과거 여기 중복 정의가 있었으나 미사용 + 값 충돌(60분 vs 7일)로 제거 — A5)
    GEMINI_API_KEY: Optional[str] = None
    BACKEND_URL: str = "http://localhost:8002"
    # 결제 개발 모드: True 면 실제 PG 검증 없이 결제 성공 처리(로컬 데모용). 운영에서는 반드시 False.
    PAYMENTS_DEV_MODE: bool = True
    # CORS 허용 오리진 (쉼표 구분). 운영 도메인 추가 시 환경변수로 지정.
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    class Config:
        env_file = env_path

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

settings = Settings()

