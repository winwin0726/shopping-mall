import os
import json
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.database import get_db

temp_json_path = os.path.join(_PROJECT_ROOT, "TEMP_CRAWLED", "crawled_products.json")

def migrate():
    db = get_db()
    existing_products = db.get_all_products()
    
    if len(existing_products) == 0 and os.path.exists(temp_json_path):
        print(f"Migrating from {temp_json_path}...")
        try:
            with open(temp_json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if data and isinstance(data, list):
                db.add_products_bulk(data)
                print(f"Successfully migrated {len(data)} items to SQLite DB.")
                
                # Backup the old json
                os.rename(temp_json_path, temp_json_path + ".bak")
        except Exception as e:
            print(f"Migration error: {e}")
    else:
        print("DB already has data or json not found.")

if __name__ == "__main__":
    migrate()
