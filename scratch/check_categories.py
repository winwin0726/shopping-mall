import os
import sqlite3

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_PATH = os.path.join(_BASE_DIR, "sql_app.db")

print(f"Connecting to DB: {_DB_PATH}")
conn = sqlite3.connect(_DB_PATH)
cursor = conn.cursor()

try:
    cursor.execute("SELECT id, parent_id, name, slug FROM categories")
    rows = cursor.fetchall()
    print("\n--- Categories ---")
    for row in rows:
        print(f"ID: {row[0]} | Parent ID: {row[1]} | Name: {row[2]} | Slug: {row[3]}")
        
    cursor.execute("SELECT COUNT(*) FROM brands")
    print(f"\nTotal brands in DB: {cursor.fetchone()[0]}")
    
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
