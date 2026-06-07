import os

admin_router_path = r"D:\에이전트그룹\LUXAI_ShoppingMall_20260605\backend\routers\admin.py"

if os.path.exists(admin_router_path):
    print("=== Admin Router Brand Endpoints ===")
    with open(admin_router_path, "r", encoding="utf-8") as f:
        in_brand_route = False
        route_lines = []
        for idx, line in enumerate(f, 1):
            if "@router." in line and "brand" in line:
                in_brand_route = True
                print(f"\nLine {idx}: {line.strip()}")
            elif in_brand_route and "@router." in line:
                in_brand_route = False
            
            if in_brand_route:
                print(f"  {line.strip()}")
else:
    print("Admin router file not found.")
