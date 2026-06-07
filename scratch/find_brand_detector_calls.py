import os

backend_dir = r"D:\에이전트그룹\LUXAI_ShoppingMall_20260605\backend"
targets = [
    os.path.join(backend_dir, "routers", "crawler.py"),
    os.path.join(backend_dir, "routers", "products.py"),
    os.path.join(backend_dir, "routers", "admin.py"),
]

for filepath in targets:
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        continue
    print(f"\n=== Searching in: {filepath} ===")
    with open(filepath, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            if "detect_brand_id" in line:
                print(f"Line {idx}: {line.strip()}")
