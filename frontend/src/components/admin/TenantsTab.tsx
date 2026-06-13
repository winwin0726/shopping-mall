"use client";
import { authFetch, API_URL } from "@/lib/api";

import { useEffect, useState } from "react";
import { 
  Users, Plus, Trash2, Edit, AlertCircle, RefreshCw, ToggleLeft, ToggleRight, Check, X, Palette,
  Sparkles, ShoppingCart, BookOpen, MessageSquare, Bot, Cpu, BarChart3, Image as ImageIcon, Layout,Grid, TrendingUp, PackageOpen
} from "lucide-react";

interface TenantData {
  id: number;
  domain: string;
  name: string;
  theme_config: {
    primaryColor?: string;
    fontFamily?: string;
    bannerTitle?: string;
    bannerSubtitle?: string;
    logoUrl?: string;
    layoutStyle?: string; // 'modern' | 'gallery' | 'card'
    gridCols?: number; // 2 | 3 | 4
    features?: {
      enable_vton?: boolean;
      enable_checkout?: boolean;
      enable_lookbook?: boolean;
      enable_reviews?: boolean;
      enable_autocrawl?: boolean;
    };
  };
  is_active: boolean;
}

interface TenantStats {
  total_sales: number;
  total_orders: number;
  shipping_stats: {
    preparing: number;
    shipping: number;
    delivered: number;
  };
  monthly_sales: Array<{
    month: string;
    amount: number;
  }>;
  is_demo: boolean;
}

export default function TenantsTab() {
  const apiUrl = API_URL;
  const [tenants, setTenants] = useState<TenantData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Settings Modal states
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingTenant, setEditingTenant] = useState<TenantData | null>(null);
  
  // Basic & Theme Form states
  const [name, setName] = useState("");
  const [domain, setDomain] = useState("");
  const [primaryColor, setPrimaryColor] = useState("#2563eb");
  const [fontFamily, setFontFamily] = useState("Inter");
  const [bannerTitle, setBannerTitle] = useState("");
  const [bannerSubtitle, setBannerSubtitle] = useState("");
  const [logoUrl, setLogoUrl] = useState("");
  const [layoutStyle, setLayoutStyle] = useState("modern");
  const [gridCols, setGridCols] = useState(3);
  const [isActive, setIsActive] = useState(true);

  // Detailed Feature Toggle States (Feature Flags)
  const [enableVton, setEnableVton] = useState(true);
  const [enableCheckout, setEnableCheckout] = useState(true);
  const [enableLookbook, setEnableLookbook] = useState(true);
  const [enableReviews, setEnableReviews] = useState(true);
  const [enableAutocrawl, setEnableAutocrawl] = useState(true);

  // Stats Modal states
  const [isStatsOpen, setIsStatsOpen] = useState(false);
  const [selectedStatsTenant, setSelectedStatsTenant] = useState<TenantData | null>(null);
  const [statsData, setStatsData] = useState<TenantStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);
  const [statsError, setStatsError] = useState<string | null>(null);

  const fetchTenants = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await authFetch(`${apiUrl}/api/admin/tenants`);
      if (!res.ok) throw new Error("테넌트 목록을 불러오는 데 실패했습니다.");
      const data = await res.json();
      setTenants(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async (tenant: TenantData) => {
    setSelectedStatsTenant(tenant);
    setIsStatsOpen(true);
    setStatsLoading(true);
    setStatsError(null);
    setStatsData(null);
    try {
      const res = await authFetch(`${apiUrl}/api/admin/tenants/${tenant.id}/stats`);
      if (!res.ok) throw new Error("테넌트 통계 데이터를 불러오는 데 실패했습니다.");
      const data = await res.json();
      setStatsData(data);
    } catch (err: any) {
      setStatsError(err.message);
    } finally {
      setStatsLoading(false);
    }
  };

  const handleOpenCreateModal = () => {
    setEditingTenant(null);
    setName("");
    setDomain("");
    setPrimaryColor("#2563eb");
    setFontFamily("Inter");
    setBannerTitle("");
    setBannerSubtitle("");
    setLogoUrl("");
    setLayoutStyle("modern");
    setGridCols(3);
    setIsActive(true);
    
    // Default features on for new tenants
    setEnableVton(true);
    setEnableCheckout(true);
    setEnableLookbook(true);
    setEnableReviews(true);
    setEnableAutocrawl(true);
    
    setIsModalOpen(true);
  };

  const handleOpenEditModal = (tenant: TenantData) => {
    setEditingTenant(tenant);
    setName(tenant.name);
    setDomain(tenant.domain);
    setPrimaryColor(tenant.theme_config?.primaryColor || "#2563eb");
    setFontFamily(tenant.theme_config?.fontFamily || "Inter");
    setBannerTitle(tenant.theme_config?.bannerTitle || "");
    setBannerSubtitle(tenant.theme_config?.bannerSubtitle || "");
    setLogoUrl(tenant.theme_config?.logoUrl || "");
    setLayoutStyle(tenant.theme_config?.layoutStyle || "modern");
    setGridCols(tenant.theme_config?.gridCols || 3);
    setIsActive(tenant.is_active);
    
    // Populate features
    const features = tenant.theme_config?.features || {};
    setEnableVton(features.enable_vton !== false);
    setEnableCheckout(features.enable_checkout !== false);
    setEnableLookbook(features.enable_lookbook !== false);
    setEnableReviews(features.enable_reviews !== false);
    setEnableAutocrawl(features.enable_autocrawl !== false);
    
    setIsModalOpen(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !domain) {
      alert("도메인과 쇼핑몰명은 필수 입력 항목입니다.");
      return;
    }

    const payload = {
      name,
      domain,
      theme_config: {
        primaryColor,
        fontFamily,
        bannerTitle,
        bannerSubtitle,
        logoUrl,
        layoutStyle,
        gridCols,
        features: {
          enable_vton: enableVton,
          enable_checkout: enableCheckout,
          enable_lookbook: enableLookbook,
          enable_reviews: enableReviews,
          enable_autocrawl: enableAutocrawl
        }
      },
      is_active: isActive
    };

    try {
      let res;
      if (editingTenant) {
        // UPDATE
        res = await authFetch(`${apiUrl}/api/admin/tenants/${editingTenant.id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
      } else {
        // CREATE
        res = await authFetch(`${apiUrl}/api/admin/tenants`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
      }

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || "테넌트 저장에 실패했습니다.");
      }

      setIsModalOpen(false);
      await fetchTenants();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleDelete = async (id: number, tenantName: string) => {
    if (!confirm(`테넌트 '${tenantName}'를 완전히 삭제하시겠습니까?\n이 작업은 되돌릴 수 없으며 소속 상품 연동에 영향이 갈 수 있습니다.`)) return;

    try {
      const res = await authFetch(`${apiUrl}/api/admin/tenants/${id}`, {
        method: "DELETE"
      });
      if (!res.ok) throw new Error("테넌트 삭제에 실패했습니다.");
      await fetchTenants();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleToggleActive = async (tenant: TenantData) => {
    const nextActive = !tenant.is_active;
    try {
      const res = await authFetch(`${apiUrl}/api/admin/tenants/${tenant.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: nextActive })
      });
      if (!res.ok) throw new Error("테넌트 상태 변경에 실패했습니다.");
      await fetchTenants();
    } catch (err: any) {
      alert(err.message);
    }
  };

  useEffect(() => {
    fetchTenants();
  }, []);

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Top Section */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 mb-2 tracking-tight">테넌트 설정 (Tenant Settings)</h2>
          <p className="text-slate-500">쇼핑몰 임대업체들의 브랜딩 로고, 메인 디자인 스타일, 매출 통계 및 기능 통제권을 관리합니다.</p>
        </div>
        <div className="flex gap-2">
          <button 
            onClick={fetchTenants} 
            className="bg-slate-100 hover:bg-slate-200 text-slate-700 px-4 py-2 rounded-lg flex items-center transition-colors border border-slate-200 font-medium"
          >
            <RefreshCw size={16} className={`mr-2 ${loading ? 'animate-spin' : ''}`} /> 새로고침
          </button>
          <button 
            onClick={handleOpenCreateModal}
            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg flex items-center transition-all shadow-sm font-medium"
          >
            <Plus size={18} className="mr-1.5" /> 새 테넌트 추가
          </button>
        </div>
      </div>

      {/* Error alert */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 p-4 rounded-lg flex items-center">
          <AlertCircle className="mr-3 text-red-500" size={20} />
          {error}
        </div>
      )}

      {/* Table Container */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                <th className="p-4 text-xs font-semibold text-slate-600 uppercase tracking-wider">ID</th>
                <th className="p-4 text-xs font-semibold text-slate-600 uppercase tracking-wider">쇼핑몰명 / 로고</th>
                <th className="p-4 text-xs font-semibold text-slate-600 uppercase tracking-wider">연동 도메인 (Domain)</th>
                <th className="p-4 text-xs font-semibold text-slate-600 uppercase tracking-wider">테마 및 레이아웃</th>
                <th className="p-4 text-xs font-semibold text-slate-600 uppercase tracking-wider">활성 상세기능 (Features)</th>
                <th className="p-4 text-xs font-semibold text-slate-600 uppercase tracking-wider">구동 상태</th>
                <th className="p-4 text-xs font-semibold text-slate-600 uppercase tracking-wider text-right">관리</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {loading ? (
                <tr>
                  <td colSpan={7} className="p-8 text-center text-slate-400">
                    로딩 중...
                  </td>
                </tr>
              ) : tenants.length === 0 ? (
                <tr>
                  <td colSpan={7} className="p-8 text-center text-slate-400">
                    등록된 테넌트 쇼핑몰이 없습니다.
                  </td>
                </tr>
              ) : (
                tenants.map((tenant) => {
                  const features = tenant.theme_config?.features || {};
                  const theme = tenant.theme_config || {};
                  return (
                    <tr key={tenant.id} className="hover:bg-slate-50 transition-colors">
                      <td className="p-4 text-slate-500 font-medium">#{tenant.id}</td>
                      <td className="p-4">
                        <div className="flex items-center gap-3">
                          {theme.logoUrl ? (
                            <img 
                              src={theme.logoUrl} 
                              alt="Logo" 
                              className="w-8 h-8 rounded bg-slate-50 object-contain border border-slate-200 p-0.5" 
                            />
                          ) : (
                            <div className="w-8 h-8 rounded bg-slate-100 flex items-center justify-center text-slate-500 border border-slate-200">
                              <ImageIcon size={14} />
                            </div>
                          )}
                          <div>
                            <div className="font-semibold text-slate-900 text-sm">{tenant.name}</div>
                            <div className="text-[10px] text-slate-500">
                              {theme.layoutStyle === "gallery" ? "AI 갤러리 룩북형" : theme.layoutStyle === "card" ? "미니멀 카드형" : "기본 모던 그리드형"} ({theme.gridCols || 3}열)
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="p-4 text-blue-600 font-mono text-sm">
                        <a href={`http://${tenant.domain}`} target="_blank" rel="noreferrer" className="hover:underline font-semibold">
                          {tenant.domain}
                        </a>
                      </td>
                      <td className="p-4 text-slate-700 text-sm">
                        <div className="flex items-center gap-2.5">
                          <span 
                            className="w-3.5 h-3.5 rounded-full border border-slate-200" 
                            style={{ backgroundColor: theme.primaryColor || "#2563eb" }}
                          />
                          <span className="bg-slate-100 text-slate-600 border border-slate-200 px-2 py-0.5 rounded text-xs font-mono">
                            {theme.fontFamily || "Inter"}
                          </span>
                        </div>
                      </td>
                      <td className="p-4">
                        <div className="flex flex-wrap gap-1.5">
                          {/* Feature Badges */}
                          <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold border ${
                            features.enable_vton !== false 
                              ? "bg-purple-50 text-purple-700 border-purple-200" 
                              : "bg-slate-100 text-slate-400 border-transparent opacity-40"
                          }`} title="가상피팅 서비스">
                            <Sparkles size={10} /> 피팅
                          </span>
                          <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold border ${
                            features.enable_checkout !== false 
                              ? "bg-blue-50 text-blue-700 border-blue-200" 
                              : "bg-slate-100 text-slate-400 border-transparent opacity-40"
                          }`} title="장바구니 결제">
                            <ShoppingCart size={10} /> 결제
                          </span>
                          <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold border ${
                            features.enable_lookbook !== false 
                              ? "bg-teal-50 text-teal-700 border-teal-200" 
                              : "bg-slate-100 text-slate-400 border-transparent opacity-40"
                          }`} title="스타일 룩북">
                            <BookOpen size={10} /> 룩북
                          </span>
                          <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold border ${
                            features.enable_reviews !== false 
                              ? "bg-amber-50 text-amber-700 border-amber-200" 
                              : "bg-slate-100 text-slate-400 border-transparent opacity-40"
                          }`} title="구매리뷰 및 QA">
                            <MessageSquare size={10} /> 소통
                          </span>
                          <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold border ${
                            features.enable_autocrawl !== false 
                              ? "bg-pink-50 text-pink-700 border-pink-200" 
                              : "bg-slate-100 text-slate-400 border-transparent opacity-40"
                          }`} title="크롤링 자동연동">
                            <Bot size={10} /> 동기화
                          </span>
                        </div>
                      </td>
                      <td className="p-4">
                        <button 
                          onClick={() => handleToggleActive(tenant)}
                          className={`inline-flex items-center gap-1.5 px-2 py-1 rounded text-xs font-semibold border transition-colors ${
                            tenant.is_active 
                              ? "bg-green-50 text-green-700 border-green-200 hover:bg-green-100" 
                              : "bg-red-50 text-red-700 border-red-200 hover:bg-red-100"
                          }`}
                        >
                          {tenant.is_active ? <ToggleRight size={14} /> : <ToggleLeft size={14} />}
                          {tenant.is_active ? "활성 구동" : "비활성 점검"}
                        </button>
                      </td>
                      <td className="p-4 text-right">
                        <div className="flex justify-end gap-1.5">
                          {/* 고도화: 매출 및 주문 통계 버튼 */}
                          <button
                            onClick={() => fetchStats(tenant)}
                            className="p-1.5 bg-blue-50 text-blue-700 hover:text-blue-900 rounded hover:bg-blue-100 border border-blue-200 transition flex items-center gap-1"
                            title="매출/주문 통계 현황"
                          >
                            <BarChart3 size={16} />
                            <span className="text-xs font-bold px-0.5">실적</span>
                          </button>
                          <button
                            onClick={() => handleOpenEditModal(tenant)}
                            className="p-1.5 bg-slate-100 text-slate-600 hover:text-slate-900 rounded hover:bg-slate-200 border border-slate-200 transition"
                            title="테넌트 설정 편집"
                          >
                            <Edit size={16} />
                          </button>
                          <button
                            onClick={() => handleDelete(tenant.id, tenant.name)}
                            className="p-1.5 bg-slate-100 text-red-600 hover:text-red-700 hover:bg-red-50 rounded border border-slate-200 transition"
                            title="테넌트 삭제"
                          >
                            <Trash2 size={16} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Editor Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 overflow-y-auto animate-in fade-in duration-200">
          <div className="bg-white border border-slate-200 w-full max-w-2xl rounded-2xl overflow-hidden shadow-xl p-6 space-y-6 my-8">
            <div className="flex justify-between items-center border-b border-slate-200 pb-4">
              <h3 className="text-xl font-bold text-slate-900 flex items-center gap-2">
                <Palette className="text-blue-600" />
                {editingTenant ? `테넌트 설정 편집 (#${editingTenant.id})` : "새 테넌트 추가"}
              </h3>
              <button onClick={() => setIsModalOpen(false)} className="text-slate-500 hover:text-slate-800">
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-6">
              {/* 기본 설정 */}
              <div className="space-y-4">
                <h4 className="text-sm font-semibold text-blue-600 border-l-4 border-blue-600 pl-2">기본 정보 설정</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-600 uppercase tracking-wider">쇼핑몰명</label>
                    <input
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="예: AI 가상피팅 명품샵"
                      className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2 text-slate-900 placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition"
                      required
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-600 uppercase tracking-wider">도메인 주소</label>
                    <input
                      type="text"
                      value={domain}
                      onChange={(e) => setDomain(e.target.value)}
                      placeholder="예: bag.mall.com"
                      className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2 text-slate-900 placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition font-mono"
                      required
                    />
                  </div>
                </div>
              </div>

              {/* 고도화: 디자인 & 레이아웃 변경 설정 */}
              <div className="border-t border-slate-200 pt-4 space-y-4">
                <h4 className="text-sm font-semibold text-blue-600 border-l-4 border-blue-600 pl-2 flex items-center gap-1.5">
                  <Layout size={16} /> 브랜드 브랜딩 및 레이아웃 제어
                </h4>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-600 uppercase tracking-wider">대표 로고 이미지 URL (Logo Image URL)</label>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={logoUrl}
                        onChange={(e) => setLogoUrl(e.target.value)}
                        placeholder="http://example.com/logo.png"
                        className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2 text-slate-900 placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition text-sm"
                      />
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-600 uppercase tracking-wider">메인 화면 레이아웃 스타일</label>
                    <select
                      value={layoutStyle}
                      onChange={(e) => setLayoutStyle(e.target.value)}
                      className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2 text-slate-800 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition text-sm"
                    >
                      <option value="modern">기본 모던 그리드형 (Modern Grid)</option>
                      <option value="gallery">AI 룩북 갤러리 강조형 (AI Gallery)</option>
                      <option value="card">미니멀 와이드 카드형 (Minimal Wide Card)</option>
                    </select>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-600 uppercase tracking-wider flex items-center gap-1">
                      <Grid size={12} /> 데스크톱 상품 노출 열 개수 (Grid System)
                    </label>
                    <div className="flex gap-4 pt-1.5">
                      {[2, 3, 4].map((num) => (
                        <label key={num} className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                          <input
                            type="radio"
                            name="gridCols"
                            value={num}
                            checked={gridCols === num}
                            onChange={() => setGridCols(num)}
                            className="w-4 h-4 border-slate-300 text-blue-600 bg-white focus:ring-0"
                          />
                          {num}열 정렬
                        </label>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              {/* UI 커스텀 테마 설정 */}
              <div className="border-t border-slate-200 pt-4 space-y-4">
                <h4 className="text-sm font-semibold text-blue-600 border-l-4 border-blue-600 pl-2">UI 타이포그래피 및 배너 설정</h4>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-600 uppercase tracking-wider">브랜드 메인 컬러</label>
                    <div className="flex gap-2">
                      <input
                        type="color"
                        value={primaryColor}
                        onChange={(e) => setPrimaryColor(e.target.value)}
                        className="w-10 h-10 bg-transparent border-0 cursor-pointer rounded overflow-hidden shrink-0"
                      />
                      <input
                        type="text"
                        value={primaryColor}
                        onChange={(e) => setPrimaryColor(e.target.value)}
                        className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2 text-slate-900 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition font-mono"
                      />
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-600 uppercase tracking-wider">기본 폰트 패밀리</label>
                    <select
                      value={fontFamily}
                      onChange={(e) => setFontFamily(e.target.value)}
                      className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2 text-slate-800 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition"
                    >
                      <option value="Inter">Inter (기본)</option>
                      <option value="Outfit">Outfit (프리미엄 럭셔리)</option>
                      <option value="Roboto">Roboto (깔끔함)</option>
                      <option value="Noto Sans KR">Noto Sans KR (한글 특화)</option>
                    </select>
                  </div>
                </div>

                {/* Banner custom Settings */}
                <div className="space-y-3">
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-600 uppercase tracking-wider">메인 배너 대제목 (Banner Title)</label>
                    <input
                      type="text"
                      value={bannerTitle}
                      onChange={(e) => setBannerTitle(e.target.value)}
                      placeholder="예: 세상에 없던 나만의 가상 피팅 룸"
                      className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2 text-slate-900 placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-600 uppercase tracking-wider">메인 배너 소제목 (Banner Subtitle)</label>
                    <input
                      type="text"
                      value={bannerSubtitle}
                      onChange={(e) => setBannerSubtitle(e.target.value)}
                      placeholder="예: 클릭 한 번으로 가상에서 마음껏 착용해보세요."
                      className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2 text-slate-900 placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition"
                    />
                  </div>
                </div>
              </div>

              {/* 쇼핑몰 기능 제어 설정 (Feature Flags) */}
              <div className="border-t border-slate-200 pt-4 space-y-4">
                <h4 className="text-sm font-semibold text-blue-600 border-l-4 border-blue-600 pl-2 flex items-center gap-1.5">
                  <Cpu size={16} /> 쇼핑몰 상세 기능 활성화 제어 (Feature Control)
                </h4>
                <p className="text-xs text-slate-500">해당 임대 쇼핑몰에서 제공할 상세 솔루션 기능들을 개별 활성화/제한할 수 있습니다.</p>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 pt-2">
                  <label className="flex items-start justify-between p-3.5 bg-slate-50/50 border border-slate-200 rounded-xl hover:bg-slate-50 hover:border-slate-300 transition cursor-pointer select-none">
                    <div className="space-y-1 pr-4">
                      <div className="flex items-center gap-1.5 text-slate-800 text-sm font-bold">
                        <Sparkles size={14} className="text-purple-600" /> AI 가상 피팅룸 활성
                      </div>
                      <p className="text-[11px] text-slate-500 leading-normal">상품 상세 페이지에서 가상 피팅(VTON) 카메라 솔루션을 활성화합니다.</p>
                    </div>
                    <input
                      type="checkbox"
                      checked={enableVton}
                      onChange={(e) => setEnableVton(e.target.checked)}
                      className="w-4 h-4 rounded border-slate-300 text-blue-600 focus:ring-0 focus:ring-offset-0 focus:outline-none bg-white mt-1"
                    />
                  </label>

                  <label className="flex items-start justify-between p-3.5 bg-slate-50/50 border border-slate-200 rounded-xl hover:bg-slate-50 hover:border-slate-300 transition cursor-pointer select-none">
                    <div className="space-y-1 pr-4">
                      <div className="flex items-center gap-1.5 text-slate-800 text-sm font-bold">
                        <ShoppingCart size={14} className="text-blue-600" /> 장바구니 및 구매/결제 활성
                      </div>
                      <p className="text-[11px] text-slate-500 leading-normal">끄면 실제 주문이 중단되며, 단순 전시용 상품 카탈로그로 전환됩니다.</p>
                    </div>
                    <input
                      type="checkbox"
                      checked={enableCheckout}
                      onChange={(e) => setEnableCheckout(e.target.checked)}
                      className="w-4 h-4 rounded border-slate-300 text-blue-600 focus:ring-0 focus:ring-offset-0 focus:outline-none bg-white mt-1"
                    />
                  </label>

                  <label className="flex items-start justify-between p-3.5 bg-slate-50/50 border border-slate-200 rounded-xl hover:bg-slate-50 hover:border-slate-300 transition cursor-pointer select-none">
                    <div className="space-y-1 pr-4">
                      <div className="flex items-center gap-1.5 text-slate-800 text-sm font-bold">
                        <BookOpen size={14} className="text-teal-600" /> AI 테마별 코디 룩북 활성
                      </div>
                      <p className="text-[11px] text-slate-500 leading-normal">인공지능 추천 코디 및 시즌 룩북 카테고리 메뉴를 쇼핑몰에 노출합니다.</p>
                    </div>
                    <input
                      type="checkbox"
                      checked={enableLookbook}
                      onChange={(e) => setEnableLookbook(e.target.checked)}
                      className="w-4 h-4 rounded border-slate-300 text-blue-600 focus:ring-0 focus:ring-offset-0 focus:outline-none bg-white mt-1"
                    />
                  </label>

                  <label className="flex items-start justify-between p-3.5 bg-slate-50/50 border border-slate-200 rounded-xl hover:bg-slate-50 hover:border-slate-300 transition cursor-pointer select-none">
                    <div className="space-y-1 pr-4">
                      <div className="flex items-center gap-1.5 text-slate-800 text-sm font-bold">
                        <MessageSquare size={14} className="text-amber-600" /> 커뮤니티 게시판 및 리뷰 활성
                      </div>
                      <p className="text-[11px] text-slate-500 leading-normal">고객의 생생한 텍스트/포토 리뷰 및 1:1 고객지원 게시판을 활성화합니다.</p>
                    </div>
                    <input
                      type="checkbox"
                      checked={enableReviews}
                      onChange={(e) => setEnableReviews(e.target.checked)}
                      className="w-4 h-4 rounded border-slate-300 text-blue-600 focus:ring-0 focus:ring-offset-0 focus:outline-none bg-white mt-1"
                    />
                  </label>

                  <label className="flex items-start justify-between p-3.5 bg-slate-50/50 border border-slate-200 rounded-xl hover:bg-slate-50 hover:border-slate-300 transition cursor-pointer select-none md:col-span-2">
                    <div className="space-y-1 pr-4">
                      <div className="flex items-center gap-1.5 text-slate-800 text-sm font-bold">
                        <Bot size={14} className="text-pink-600" /> 본사 자동화 크롤러 상품 자동 동기화
                      </div>
                      <p className="text-[11px] text-slate-500 leading-normal">본사 AI 수집기가 새로 승인한 해외 상품들을 이 쇼핑몰에 실시간 자동 연동합니다.</p>
                    </div>
                    <input
                      type="checkbox"
                      checked={enableAutocrawl}
                      onChange={(e) => setEnableAutocrawl(e.target.checked)}
                      className="w-4 h-4 rounded border-slate-300 text-blue-600 focus:ring-0 focus:ring-offset-0 focus:outline-none bg-white mt-1"
                    />
                  </label>
                </div>
              </div>

              {/* Activation */}
              <div className="flex items-center gap-3 border-t border-slate-200 pt-4">
                <input
                  type="checkbox"
                  id="isActiveForm"
                  checked={isActive}
                  onChange={(e) => setIsActive(e.target.checked)}
                  className="w-4 h-4 rounded border-slate-300 text-blue-600 focus:ring-0 focus:ring-offset-0 focus:outline-none bg-white"
                />
                <label htmlFor="isActiveForm" className="text-sm font-semibold text-slate-700 cursor-pointer">
                  테넌트 쇼핑몰 구동 상태 활성화 (영업 개시)
                </label>
              </div>

              {/* Action Buttons */}
              <div className="flex justify-end gap-3 border-t border-slate-200 pt-4 mt-6">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="bg-slate-100 hover:bg-slate-200 text-slate-700 px-4 py-2 rounded-lg transition border border-slate-200 font-semibold"
                >
                  취소
                </button>
                <button
                  type="submit"
                  className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg font-medium transition shadow-sm flex items-center gap-1.5"
                >
                  <Check size={18} />
                  저장하기
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 고도화: 매출 및 주문 현황 통계 모달 (Stats Modal) */}
      {isStatsOpen && selectedStatsTenant && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-md p-4 overflow-y-auto animate-in fade-in duration-200">
          <div className="bg-white border border-slate-200 w-full max-w-2xl rounded-2xl overflow-hidden shadow-xl p-6 space-y-6 my-8">
            <div className="flex justify-between items-center border-b border-slate-200 pb-4">
              <div>
                <h3 className="text-xl font-bold text-slate-900 flex items-center gap-2">
                  <TrendingUp className="text-blue-600" />
                  {selectedStatsTenant.name} 실적 통계 리포트
                </h3>
                <p className="text-xs text-slate-500 mt-1">도메인: {selectedStatsTenant.domain}</p>
              </div>
              <button onClick={() => setIsStatsOpen(false)} className="text-slate-500 hover:text-slate-800 bg-slate-100 hover:bg-slate-200 p-1.5 rounded-lg transition">
                <X size={18} />
              </button>
            </div>

            {statsLoading ? (
              <div className="py-20 flex flex-col items-center justify-center text-slate-600">
                <RefreshCw className="animate-spin text-blue-600 mb-3" size={32} />
                <p>실시간 매출 및 주문 내역을 집계 중입니다...</p>
              </div>
            ) : statsError ? (
              <div className="bg-red-50 border border-red-200 text-red-800 p-4 rounded-lg flex items-center">
                <AlertCircle className="mr-3 text-red-500" size={20} />
                {statsError}
              </div>
            ) : statsData ? (
              <div className="space-y-6">
                {/* Stats Cards Row */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* 누적 매출 */}
                  <div className="bg-blue-50/50 border border-blue-200/60 p-5 rounded-xl flex flex-col justify-between shadow-sm">
                    <span className="text-xs font-semibold text-slate-600 uppercase tracking-wider">누적 총 매출액 (Sales)</span>
                    <div className="flex items-baseline gap-1 mt-3">
                      <span className="text-3xl font-black text-slate-900 tracking-tight">
                        {statsData.total_sales.toLocaleString()}
                      </span>
                      <span className="text-sm font-bold text-slate-700">원</span>
                    </div>
                    {statsData.is_demo && (
                      <span className="text-[10px] text-blue-700 bg-blue-50 border border-blue-200 px-2 py-0.5 rounded self-start mt-2 font-semibold">
                        데모 시뮬레이션 데이터
                      </span>
                    )}
                  </div>

                  {/* 누적 주문 건수 */}
                  <div className="bg-purple-50/50 border border-purple-200/60 p-5 rounded-xl flex flex-col justify-between shadow-sm">
                    <span className="text-xs font-semibold text-slate-600 uppercase tracking-wider">누적 주문 건수 (Orders)</span>
                    <div className="flex items-baseline gap-1 mt-3">
                      <span className="text-3xl font-black text-slate-900 tracking-tight">
                        {statsData.total_orders.toLocaleString()}
                      </span>
                      <span className="text-sm font-bold text-slate-700">건</span>
                    </div>
                    <span className="text-[10px] text-slate-500 mt-2 font-medium">
                      건당 평균 단가: {Math.round(statsData.total_sales / (statsData.total_orders || 1)).toLocaleString()} 원
                    </span>
                  </div>
                </div>

                {/* 주문 처리 상태 현황 */}
                <div className="bg-slate-50 border border-slate-200 p-4 rounded-xl space-y-3.5 shadow-sm">
                  <h4 className="text-sm font-bold text-slate-800 flex items-center gap-1.5">
                    <PackageOpen size={16} className="text-amber-600" /> 실시간 물류 및 주문 처리 현황
                  </h4>
                  
                  <div className="grid grid-cols-3 gap-2 text-center">
                    <div className="bg-white border border-slate-200 p-3 rounded-lg shadow-sm">
                      <div className="text-xs text-slate-600 font-semibold mb-1">배송 준비 중</div>
                      <div className="text-xl font-bold text-amber-800 font-mono">
                        {statsData.shipping_stats.preparing} <span className="text-xs text-slate-500">건</span>
                      </div>
                    </div>
                    <div className="bg-white border border-slate-200 p-3 rounded-lg shadow-sm">
                      <div className="text-xs text-slate-600 font-semibold mb-1">배송 중</div>
                      <div className="text-xl font-bold text-blue-700 font-mono">
                        {statsData.shipping_stats.shipping} <span className="text-xs text-slate-500">건</span>
                      </div>
                    </div>
                    <div className="bg-white border border-slate-200 p-3 rounded-lg shadow-sm">
                      <div className="text-xs text-slate-600 font-semibold mb-1">배송 완료</div>
                      <div className="text-xl font-bold text-green-700 font-mono">
                        {statsData.shipping_stats.delivered} <span className="text-xs text-slate-500">건</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* 월별 매출 그래프 */}
                <div className="bg-slate-50 border border-slate-200 p-5 rounded-xl space-y-4 shadow-sm">
                  <h4 className="text-sm font-bold text-slate-800">최근 6개월 매출 추이</h4>
                  <div className="h-44 flex items-end justify-between gap-4 pt-6 px-2">
                    {statsData.monthly_sales.map((item, index) => {
                      // 최대 매출액을 기준으로 퍼센트 비율 계산
                      const maxAmount = Math.max(...statsData.monthly_sales.map(m => m.amount));
                      const heightPercent = maxAmount > 0 ? (item.amount / maxAmount) * 100 : 0;
                      
                      return (
                        <div key={index} className="flex-1 flex flex-col items-center gap-2 group h-full justify-end">
                          {/* 툴팁 팝업 */}
                          <div className="bg-slate-900 text-[10px] text-white py-1 px-1.5 rounded opacity-0 group-hover:opacity-100 transition duration-150 shadow-lg font-semibold pointer-events-none mb-1 font-mono">
                            {(item.amount / 10000).toFixed(0)} 만원
                          </div>
                          {/* 막대 바 */}
                          <div 
                            className="w-full bg-gradient-to-t from-blue-600 to-indigo-500 rounded-t hover:from-blue-500 hover:to-indigo-400 transition-all duration-300"
                            style={{ height: `${Math.max(5, heightPercent * 0.85)}%` }}
                          />
                          {/* 월 이름 */}
                          <span className="text-xs text-slate-600 font-semibold">{item.month}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* 닫기 버튼 */}
                <div className="flex justify-end border-t border-slate-200 pt-4 mt-6">
                  <button
                    onClick={() => setIsStatsOpen(false)}
                    className="bg-slate-100 hover:bg-slate-200 text-slate-700 px-5 py-2.5 rounded-lg transition text-sm font-semibold border border-slate-200"
                  >
                    확인 및 닫기
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
