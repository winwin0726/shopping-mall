import io
import os

file_path = r'd:\\에이전트그룹\\쇼핑몰\\frontend\\src\\app\\admin\\page.tsx'

with io.open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

new_sidebar = [
    '            <SidebarItem icon={<BarChart3 />} label="대시보드" active={activeTab === "overview"} onClick={() => setActiveTab("overview")} />\n',
    '            <SidebarItem icon={<Box />} label="AI 자동화 파이프라인" active={activeTab === "pipeline"} onClick={() => setActiveTab("pipeline")} />\n',
    '            <SidebarItem icon={<Tags />} label="카테고리 관리" active={activeTab === "categories"} onClick={() => setActiveTab("categories")} />\n',
    '            <SidebarItem icon={<Package />} label="상품 관리" active={activeTab === "products"} onClick={() => setActiveTab("products")} />\n',
    '            <SidebarItem icon={<UserCog />} label="회원 관리" active={activeTab === "users"} onClick={() => setActiveTab("users")} />\n',
    '            <SidebarItem icon={<CreditCard />} label="결제 및 주문" active={activeTab === "orders"} onClick={() => setActiveTab("orders")} />\n',
    '            <SidebarItem icon={<Users />} label="테넌트 설정" active={activeTab === "tenants"} onClick={() => setActiveTab("tenants")} />\n'
]

lines[40:47] = new_sidebar

# Fix dummy traffic data strings that had broken quotes causing TS syntax errors
for i in range(15, 23):
    if "revenue:" in lines[i]:
        parts = lines[i].split("revenue:")
        name_placeholder = f"Day {i-14}"
        lines[i] = f"  {{ name: \"{name_placeholder}\", revenue:{parts[1]}"

# Fix imports
for i in range(5, 12):
    if "Plus, Trash2, Search, Package" in lines[i]:
        lines[i] = '  Plus, Trash2, Search, Package, UserCog\n'

# Fix logout Text
for i in range(45, 55):
    if "<LogOut size={18}" in lines[i]:
        lines[i] = '            <LogOut size={18} className="mr-3" /> 로그아웃\n'

with io.open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("page.tsx encoding issues fixed successfully.")
