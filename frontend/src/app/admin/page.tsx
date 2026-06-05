"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  BarChart3, Users, Tags, CreditCard, Box, LogOut, Package, UserCog, Zap, MessageSquare, Palette, Home
} from "lucide-react";
import Link from "next/link";
import { API_URL, authFetch } from "@/lib/api";

// Components
import OverviewTab from "@/components/admin/OverviewTab";
import PipelineTab from "@/components/admin/PipelineTab";
import CategoriesTab from "@/components/admin/CategoriesTab";
import ProductsTab from "@/components/admin/ProductsTab";
import UsersTab from "@/components/admin/UsersTab";
import OrdersTab from "@/components/admin/OrdersTab";
import TenantsTab from "@/components/admin/TenantsTab";
import SupportTab from "@/components/admin/SupportTab";
import DesignTab from "@/components/admin/DesignTab";

export default function AdminDashboard() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState("overview");
  const [tenant, setTenant] = useState<any>(null);
  const [adminEmail, setAdminEmail] = useState("");
  const [authState, setAuthState] = useState<"checking" | "authorized" | "denied">("checking");

  // 관리자 권한 가드: 백엔드 JWT 검증 후 role === "ADMIN" 인 경우에만 접근 허용
  useEffect(() => {
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    if (!token) { setAuthState("denied"); return; }
    authFetch(`${API_URL}/api/auth/me`)
      .then(r => (r.ok ? r.json() : null))
      .then(data => {
        if (data && data.role === "ADMIN") {
          setAdminEmail(data.email);
          setAuthState("authorized");
        } else {
          setAuthState("denied");
        }
      })
      .catch(() => setAuthState("denied"));
  }, []);

  // 권한 없음 → 잠시 후 로그인 페이지로 리다이렉트
  useEffect(() => {
    if (authState !== "denied") return;
    const t = setTimeout(() => router.push("/login"), 1500);
    return () => clearTimeout(t);
  }, [authState, router]);

  // 인증된 관리자에 한해 테넌트 정보(로고/제목) 로드
  useEffect(() => {
    if (authState !== "authorized") return;
    authFetch(`${API_URL}/api/admin/tenants`)
      .then(r => r.ok ? r.json() : [])
      .then(tenants => {
        const hq = tenants.find((t: any) => t.domain === "hq.mall.com") || tenants[0];
        if (hq) setTenant(hq);
      })
      .catch(() => {});
  }, [authState]);

  const handleLogout = () => {
    localStorage.removeItem("token");
    router.push("/login");
  };

  if (authState === "checking") {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-950 text-slate-300">
        권한 확인 중…
      </div>
    );
  }
  if (authState === "denied") {
    return (
      <div className="flex h-screen flex-col items-center justify-center bg-slate-950 text-slate-300 gap-3">
        <p className="text-lg font-bold text-white">관리자 권한이 필요합니다</p>
        <p className="text-sm text-slate-400">로그인 페이지로 이동합니다…</p>
      </div>
    );
  }

  const SidebarItem = ({ icon, label, active, onClick }: { icon: React.ReactNode, label: string, active: boolean, onClick: () => void }) => (
    <button
      onClick={onClick}
      className={`flex items-center w-full px-6 py-3 text-sm font-medium transition-colors ${
        active 
          ? "bg-blue-600/10 text-blue-500 border-r-4 border-blue-500" 
          : "text-slate-400 hover:text-white hover:bg-slate-800/50 border-r-4 border-transparent"
      }`}
    >
      <span className="mr-3">{icon}</span>
      {label}
    </button>
  );

  return (
    <div className="flex h-screen bg-slate-950 text-slate-300 font-sans">
      {/* 1. Left Sidebar (LNB) */}
      <aside className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col">
        <div className="h-16 flex items-center px-6 border-b border-slate-800 shrink-0">
          <h1 className="text-xl font-bold text-white flex items-center tracking-tight">
            {tenant?.theme_config?.logoUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={tenant.theme_config.logoUrl}
                alt="Logo"
                className="w-8 h-8 rounded-full object-cover mr-2.5 border border-slate-700 bg-white"
              />
            ) : (
              <Zap className="text-blue-500 mr-2" size={24} />
            )}
            {tenant?.name || "LUXAI"}
          </h1>
        </div>
        <nav className="py-4 space-y-1 flex-1 overflow-y-auto">
          <SidebarItem icon={<BarChart3 />} label="대시보드" active={activeTab === "overview"} onClick={() => setActiveTab("overview")} />
          <SidebarItem icon={<Box />} label="AI 자동화 파이프라인" active={activeTab === "pipeline"} onClick={() => setActiveTab("pipeline")} />
          <SidebarItem icon={<Tags />} label="카테고리 관리" active={activeTab === "categories"} onClick={() => setActiveTab("categories")} />
          <SidebarItem icon={<Package />} label="상품 관리" active={activeTab === "products"} onClick={() => setActiveTab("products")} />
          <SidebarItem icon={<UserCog />} label="회원 관리" active={activeTab === "users"} onClick={() => setActiveTab("users")} />
          <SidebarItem icon={<CreditCard />} label="결제 및 주문현황" active={activeTab === "orders"} onClick={() => setActiveTab("orders")} />
          <SidebarItem icon={<Users />} label="테넌트 설정" active={activeTab === "tenants"} onClick={() => setActiveTab("tenants")} />
          <SidebarItem icon={<Palette />} label="디자인 설정" active={activeTab === "design"} onClick={() => setActiveTab("design")} />
          <SidebarItem icon={<MessageSquare />} label="1:1 문의 관리" active={activeTab === "support"} onClick={() => setActiveTab("support")} />
          <Link href="/" className="flex items-center w-full px-6 py-3 text-sm font-medium text-slate-400 hover:text-white hover:bg-slate-800/50 border-r-4 border-transparent transition-colors">
            <Home size={18} className="mr-3 text-blue-500" /> 쇼핑몰 홈으로 가기
          </Link>
          <button onClick={handleLogout} className="flex items-center w-full px-6 py-3 text-sm font-medium text-slate-400 hover:text-red-400 hover:bg-red-950/20 border-r-4 border-transparent transition-colors">
            <LogOut size={18} className="mr-3 text-red-500/80" /> 로그아웃
          </button>
        </nav>
        
      </aside>

      {/* 2. Main Content Area */}
      <main className="flex-1 flex flex-col h-full overflow-hidden">
        {/* Top Header */}
        <header className="h-16 bg-slate-900 border-b border-slate-800 flex items-center justify-between px-8 shrink-0">
          <h2 className="text-lg font-semibold text-white">
            {activeTab === "overview" && "대시보드"}
            {activeTab === "pipeline" && "AI 파이프라인"}
            {activeTab === "categories" && "카테고리 관리"}
            {activeTab === "products" && "상품 관리"}
            {activeTab === "users" && "회원 관리"}
            {activeTab === "orders" && "주문 및 결제"}
            {activeTab === "tenants" && "테넌트 설정"}
            {activeTab === "design" && "디자인 설정"}
            {activeTab === "support" && "1:1 문의 관리"}
          </h2>
          <div className="flex items-center space-x-4">
            <div className="text-sm">
              <span className="text-slate-400 mr-2">Logged in as</span>
              <span className="text-white font-medium">{adminEmail || "Admin"}</span>
            </div>
            <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white font-bold">
              {adminEmail?.charAt(0).toUpperCase() || "A"}
            </div>
          </div>
        </header>

        {/* Scrollable Work Area */}
        <div className="flex-1 overflow-auto p-8 bg-slate-950">
          {activeTab === "overview" && <OverviewTab />}
          {activeTab === "pipeline" && <PipelineTab />}
          {activeTab === "categories" && <CategoriesTab />}
          {activeTab === "products" && <ProductsTab />}
          {activeTab === "users" && <UsersTab />}
          {activeTab === "orders" && <OrdersTab />}
          {activeTab === "tenants" && <TenantsTab />}
          {activeTab === "design" && <DesignTab onThemeUpdate={(t: any) => setTenant(t)} />}
          {activeTab === "support" && <SupportTab />}
        </div>
      </main>
    </div>
  );
}
