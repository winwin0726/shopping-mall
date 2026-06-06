# -*- coding: utf-8 -*-
"""부팅 시 1회 실행되는 경량 마이그레이션 (SQLite 전용 PRAGMA 기반) — G1.

기존에는 main.py 안에 video_url 추가 / orders 컬럼 추가 / datetime 정규화가
제각각 try-블록으로 흩어져 있었다. 이를 단일 진입점으로 통합한다.
(정식 운영에서는 alembic 도입을 권장하나, SQLite 데모 단계에서는 create_all +
아래 보정으로 일관 처리한다.)
"""
import logging
from sqlalchemy import text

logger = logging.getLogger(__name__)

# 테이블별로 보장해야 할 추가 컬럼 {테이블: {컬럼명: DDL}}
_ENSURE_COLUMNS = {
    "hq_products": {"video_url": "TEXT", "wholesale_price": "INTEGER DEFAULT 0"},
    "orders": {"discount_amount": "INTEGER DEFAULT 0", "used_points": "INTEGER DEFAULT 0"},
    # [윈윈 도킹] 카테고리별 소매 마진
    "categories": {"margin_type": "TEXT DEFAULT 'percent'", "margin_value": "REAL DEFAULT 30.0"},
}

# ISO 'Z'/'T' 형식이 들어오면 Python 3.10 SQLAlchemy 가 파싱 실패 → 정규화 대상 datetime 컬럼
_DT_COLUMNS = {
    "hq_products": ["created_at"],
    "orders": ["created_at"],
    "users": ["created_at", "last_visit_reward_at"],
    "cart_items": ["created_at"],
    "wishlist_items": ["created_at"],
    "reviews": ["created_at"],
    "support_tickets": ["created_at", "answered_at"],
    "coupons": ["created_at"],
    "address_book": ["created_at"],
}


def _table_columns(conn, table: str) -> set:
    return {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})")).fetchall()}


def run_lightweight_migrations(engine) -> None:
    """create_all 이후 보강: ① 누락 컬럼 추가 ② datetime 문자열 정규화.
    SQLite 전용. 다른 DB(PostgreSQL 등)에서는 조용히 건너뛴다."""
    try:
        if not engine.url.get_backend_name().startswith("sqlite"):
            return
        with engine.connect() as conn:
            # ① 누락 컬럼 추가
            for table, cols in _ENSURE_COLUMNS.items():
                existing = _table_columns(conn, table)
                for col, ddl in cols.items():
                    if col not in existing:
                        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))
                        logger.info(f"[migrate] {table}.{col} 컬럼 추가")
            # ② datetime 'Z'/'T' 정규화 (외부 임포트/데모데이터 보정)
            for table, cols in _DT_COLUMNS.items():
                existing = _table_columns(conn, table)
                for col in cols:
                    if col in existing:
                        conn.execute(text(
                            f"UPDATE {table} SET {col} = REPLACE(REPLACE({col}, 'T', ' '), 'Z', '') "
                            f"WHERE {col} LIKE '%T%' OR {col} LIKE '%Z'"
                        ))
            conn.commit()
    except Exception as e:
        logger.warning(f"[migrate] 경량 마이그레이션 스킵: {e}")
