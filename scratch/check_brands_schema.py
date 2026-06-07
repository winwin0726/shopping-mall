import sqlite3
import os

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_PATH = os.path.join(_BASE_DIR, "sql_app.db")

conn = sqlite3.connect(_DB_PATH)
cursor = conn.cursor()
try:
    cursor.execute("PRAGMA table_info(brands)")
    columns = cursor.fetchall()
    print("=== Brands Table Columns ===")
    for col in columns:
        print(f"ID: {col[0]} | Name: {col[1]} | Type: {col[2]} | Default Value: {col[4]}")
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
