from datetime import datetime, timedelta
import os
import logging
import bcrypt
from jose import jwt, JWTError

logger = logging.getLogger(__name__)

# 운영에서는 환경변수 JWT_SECRET_KEY 로 반드시 교체할 것 (기본값은 로컬 개발용)
_DEV_SECRET = "supersafesecretkey_for_this_AI_fashion_mall_2026"
SECRET_KEY = os.getenv("JWT_SECRET_KEY", _DEV_SECRET)
if SECRET_KEY == _DEV_SECRET:
    # B5: 노출된 개발용 기본 시크릿 사용 시 기동 경고 (운영 위험 명시)
    logger.warning(
        "[보안] JWT_SECRET_KEY 미설정 — 개발용 기본 시크릿 사용 중. "
        "운영 배포 전 반드시 고유한 JWT_SECRET_KEY 환경변수를 설정하세요."
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
