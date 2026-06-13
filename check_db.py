import os
import sys
from sqlalchemy import create_engine, text

# DB 파일 경로
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_DB_PATH = os.path.join(_BASE_DIR, "sql_app.db")

print(f"Target DB Path: {_DB_PATH}")
if not os.path.exists(_DB_PATH):
    print("❌ DB File not found!")
    sys.exit(1)

engine = create_engine(f"sqlite:///{_DB_PATH}")

try:
    with engine.connect() as conn:
        # users 테이블 구조 및 데이터 쿼리
        res = conn.execute(text("SELECT id, email, name, role, grade FROM users")).fetchall()
        print("\n--- Registered Users List ---")
        if not res:
            print("No users found in database.")
        for row in res:
            print(f"ID: {row[0]} | Email: {row[1]} | Name: {row[2]} | Role: {row[3]} | Grade: {row[4]}")
            
        # 테이블 내에 실제로 어떤 데이터들이 있는지 전체 조회
        tables = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
        print("\n--- DB Tables & Counts ---")
        for table in tables:
            tname = table[0]
            if tname == 'sqlite_sequence':
                continue
            cnt = conn.execute(text(f"SELECT COUNT(*) FROM {tname}")).scalar()
            print(f"Table: {tname} | Count: {cnt}")
except Exception as e:
    print(f"❌ DB Query Failed: {e}")
