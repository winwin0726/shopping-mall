"use client";
import { authFetch, API_URL } from "@/lib/api";

import { useEffect, useState } from "react";
import {
  Tags, Plus, Trash2, Loader2, AlertCircle, RefreshCw,
  FolderTree, ChevronRight, X, Sparkles, Check, ToggleLeft, ToggleRight
} from "lucide-react";

interface Category {
  id: number;
  name: string;
  slug: string;
  parent_id: number | null;
  margin_type?: string;   // 'percent' | 'fixed' (윈윈 도킹: 도매가→소매가 마진)
  margin_value?: number;  // percent면 %, fixed면 원
}

interface Brand {
  id: number;
  name: string;
  eng_name: string;
  slug: string;
  logo_url: string | null;
  is_premium: boolean;
  is_active: boolean;
}

export default function CategoriesTab() {
  const apiUrl = API_URL;
  const [activeTab, setActiveTab] = useState<"category" | "brand">("category");

  // -----------------------------------------------------------------
  // 1. 카테고리 관리 상태 및 로직
  // -----------------------------------------------------------------
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showForm, setShowForm] = useState(false);
  const [newName, setNewName] = useState("");
  const [newSlug, setNewSlug] = useState("");
  const [newParentId, setNewParentId] = useState<number | "">("");
  const [submitting, setSubmitting] = useState(false);
  const [savingMargin, setSavingMargin] = useState<number | null>(null);

  const fetchCategories = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await authFetch(`${apiUrl}/api/admin/categories`);
      if (!res.ok) throw new Error("카테고리 목록을 불러올 수 없습니다.");
      const data = await res.json();
      setCategories(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!newName.trim() || !newSlug.trim()) {
      alert("카테고리 이름과 슬러그를 모두 입력해주세요.");
      return;
    }
    setSubmitting(true);
    try {
      const body: any = { name: newName.trim(), slug: newSlug.trim() };
      if (newParentId !== "") body.parent_id = Number(newParentId);

      const res = await authFetch(`${apiUrl}/api/admin/category`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "생성 실패");
      }
      setNewName("");
      setNewSlug("");
      setNewParentId("");
      setShowForm(false);
      fetchCategories();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`"${name}" 카테고리를 삭제하시겠습니까? 하위 카테고리와 연결된 상품이 있으면 문제가 생길 수 있습니다.`)) return;
    try {
      const res = await authFetch(`${apiUrl}/api/admin/category/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error("삭제 실패");
      setCategories((prev) => prev.filter((c) => c.id !== id));
    } catch (err: any) {
      alert(err.message);
    }
  };

  const updateCatField = (id: number, field: "margin_type" | "margin_value", val: any) => {
    setCategories((prev) => prev.map((c) => (c.id === id ? { ...c, [field]: val } : c)));
  };

  const saveMargin = async (cat: Category) => {
    setSavingMargin(cat.id);
    try {
      const res = await authFetch(`${apiUrl}/api/admin/category/${cat.id}/margin?recompute=true`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          margin_type: cat.margin_type || "percent",
          margin_value: Number(cat.margin_value ?? 30),
        }),
      });
      if (!res.ok) throw new Error("마진 저장에 실패했습니다.");
      const d = await res.json();
      alert(`✅ "${cat.name}" 마진 저장 완료 (기존 상품 ${d.recomputed_products ?? 0}개 소매가 재계산)`);
    } catch (err: any) {
      alert(err.message);
    } finally {
      setSavingMargin(null);
    }
  };

  // -----------------------------------------------------------------
  // 2. 브랜드 관리 상태 및 로직
  // -----------------------------------------------------------------
  const [brands, setBrands] = useState<Brand[]>([]);
  const [brandLoading, setBrandLoading] = useState(false);
  const [showBrandForm, setShowBrandForm] = useState(false);
  const [newBrandName, setNewBrandName] = useState("");
  const [newBrandEngName, setNewBrandEngName] = useState("");
  const [newBrandSlug, setNewBrandSlug] = useState("");
  const [newBrandLogo, setNewBrandLogo] = useState("");
  const [newBrandPremium, setNewBrandPremium] = useState(false);
  const [brandSubmitting, setBrandSubmitting] = useState(false);

  const fetchBrands = async () => {
    setBrandLoading(true);
    try {
      const res = await authFetch(`${apiUrl}/api/admin/brands`);
      if (!res.ok) throw new Error("브랜드 목록을 불러올 수 없습니다.");
      const data = await res.json();
      setBrands(data);
    } catch (err: any) {
      console.warn("Failed to fetch brands", err);
    } finally {
      setBrandLoading(false);
    }
  };

  const handleCreateBrand = async () => {
    if (!newBrandName.trim() || !newBrandEngName.trim() || !newBrandSlug.trim()) {
      alert("브랜드 한글명, 영문명, 슬러그를 모두 입력해주세요.");
      return;
    }
    setBrandSubmitting(true);
    try {
      const res = await authFetch(`${apiUrl}/api/admin/brand`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newBrandName.trim(),
          eng_name: newBrandEngName.trim(),
          slug: newBrandSlug.trim(),
          logo_url: newBrandLogo.trim() || null,
          is_premium: newBrandPremium,
          is_active: true
        }),
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "브랜드 생성 실패");
      }
      setNewBrandName("");
      setNewBrandEngName("");
      setNewBrandSlug("");
      setNewBrandLogo("");
      setNewBrandPremium(false);
      setShowBrandForm(false);
      fetchBrands();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setBrandSubmitting(false);
    }
  };

  const handleToggleBrandFlag = async (brand: Brand, field: "is_premium" | "is_active") => {
    try {
      const res = await authFetch(`${apiUrl}/api/admin/brand/${brand.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          [field]: !brand[field],
        }),
      });
      if (!res.ok) throw new Error("브랜드 상태 수정 실패");
      setBrands((prev) =>
        prev.map((b) => (b.id === brand.id ? { ...b, [field]: !b[field] } : b))
      );
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleDeleteBrand = async (id: number, name: string) => {
    if (!confirm(`"${name}" 브랜드를 정말 삭제하시겠습니까? 연결된 상품들의 브랜드는 '미지정'으로 변경됩니다.`)) return;
    try {
      const res = await authFetch(`${apiUrl}/api/admin/brand/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error("브랜드 삭제 실패");
      setBrands((prev) => prev.filter((b) => b.id !== id));
    } catch (err: any) {
      alert(err.message);
    }
  };

  // -----------------------------------------------------------------
  // 3. 마운트 시 데이터 로드
  // -----------------------------------------------------------------
  useEffect(() => {
    fetchCategories();
    fetchBrands();
  }, []);

  // -----------------------------------------------------------------
  // 4. UI 렌더링 헬퍼
  // -----------------------------------------------------------------
  const renderMargin = (cat: Category) => (
    <div className="flex items-center gap-1 shrink-0" title="윈윈 도매가에 얹을 소매 마진">
      <input
        type="number"
        value={cat.margin_value ?? 30}
        onChange={(e) => updateCatField(cat.id, "margin_value", e.target.value === "" ? "" : Number(e.target.value))}
        className="w-14 bg-slate-800 border border-slate-700 rounded px-1.5 py-1 text-white text-xs text-right focus:outline-none focus:border-emerald-500"
      />
      <select
        value={cat.margin_type ?? "percent"}
        onChange={(e) => updateCatField(cat.id, "margin_type", e.target.value)}
        className="bg-slate-800 border border-slate-700 rounded px-1 py-1 text-white text-xs focus:outline-none focus:border-emerald-500"
      >
        <option value="percent">%</option>
        <option value="fixed">원</option>
      </select>
      <button
        onClick={() => saveMargin(cat)}
        disabled={savingMargin === cat.id}
        className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs px-2 py-1 rounded font-bold disabled:opacity-50 cursor-pointer"
      >
        {savingMargin === cat.id ? "..." : "저장"}
      </button>
    </div>
  );

  const topLevel = categories.filter((c) => !c.parent_id);
  const getChildren = (parentId: number) => categories.filter((c) => c.parent_id === parentId);

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      
      {/* 탭 네비게이션 */}
      <div className="flex border-b border-slate-800 gap-6">
        <button
          onClick={() => setActiveTab("category")}
          className={`pb-3 text-sm font-bold border-b-2 px-1 cursor-pointer transition ${
            activeTab === "category" 
              ? "border-blue-500 text-blue-450" 
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          품목 카테고리 관리
        </button>
        <button
          onClick={() => setActiveTab("brand")}
          className={`pb-3 text-sm font-bold border-b-2 px-1 cursor-pointer transition ${
            activeTab === "brand" 
              ? "border-blue-500 text-blue-450" 
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          수입 브랜드 관리
        </button>
      </div>

      {activeTab === "category" ? (
        <>
          {/* 품목 카테고리 뷰 */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <h2 className="text-xl font-bold text-white mb-1 tracking-tight">품목 카테고리 설정 (Category Tree)</h2>
              <p className="text-slate-400 text-xs">
                대분류/중분류 카테고리를 생성·관리하고, <span className="text-emerald-400 font-semibold">소매 마진율</span>(도매가 → 소매가 자동환산 비율)을 설정합니다. 총 <span className="text-white font-bold">{categories.length}</span>개
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => setShowForm(!showForm)}
                className={`px-4 py-2 rounded-lg flex items-center font-semibold text-sm transition-colors shadow-lg cursor-pointer ${
                  showForm ? "bg-slate-700 text-slate-350" : "bg-blue-600 hover:bg-blue-500 text-white shadow-blue-900/30"
                }`}
              >
                {showForm ? <X size={15} className="mr-1.5" /> : <Plus size={15} className="mr-1.5" />}
                {showForm ? "닫기" : "새 카테고리"}
              </button>
              <button
                onClick={fetchCategories}
                className="bg-slate-800 hover:bg-slate-700 text-white px-3 py-2 rounded-lg flex items-center text-sm transition-colors cursor-pointer"
              >
                <RefreshCw size={14} className={`mr-1.5 ${loading ? "animate-spin text-blue-400" : ""}`} /> 새로고침
              </button>
            </div>
          </div>

          {/* 새 카테고리 추가 폼 */}
          {showForm && (
            <div className="bg-slate-900 border border-blue-500/30 rounded-2xl p-6 shadow-xl shadow-blue-900/10">
              <h3 className="text-md font-bold text-white mb-4 flex items-center gap-2">
                <Plus size={18} className="text-blue-450" /> 새 카테고리 추가
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs text-slate-400 font-medium mb-1.5">카테고리 이름</label>
                  <input
                    type="text"
                    placeholder="예: 여성 의류"
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2 text-white text-sm placeholder:text-slate-500 focus:outline-none focus:border-blue-500 transition"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-400 font-medium mb-1.5">슬러그 (URL)</label>
                  <input
                    type="text"
                    placeholder="예: women-clothing"
                    value={newSlug}
                    onChange={(e) => setNewSlug(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2 text-white text-sm placeholder:text-slate-500 focus:outline-none focus:border-blue-500 transition"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-400 font-medium mb-1.5">상위 카테고리 (선택)</label>
                  <select
                    value={newParentId}
                    onChange={(e) => setNewParentId(e.target.value === "" ? "" : Number(e.target.value))}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 transition"
                  >
                    <option value="">없음 (최상위)</option>
                    {topLevel.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="mt-5 flex justify-end">
                <button
                  onClick={handleCreate}
                  disabled={submitting}
                  className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-2 rounded-xl font-bold text-sm transition disabled:opacity-50 shadow-lg cursor-pointer"
                >
                  {submitting ? "생성 중..." : "카테고리 생성"}
                </button>
              </div>
            </div>
          )}

          {error && (
            <div className="bg-red-900/40 border border-red-850 text-red-200 p-4 rounded-xl flex items-center">
              <AlertCircle className="mr-3 text-red-500" size={20} />
              {error}
            </div>
          )}

          {/* 카테고리 트리 목록 */}
          {loading ? (
            <div className="flex flex-col items-center justify-center p-16 text-slate-550">
              <Loader2 size={36} className="animate-spin text-blue-500 mb-4" />
              <p className="text-sm">카테고리 데이터를 불러오고 있습니다...</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {topLevel.map((parent) => {
                const children = getChildren(parent.id);
                return (
                  <div
                    key={parent.id}
                    className="bg-slate-900 border border-slate-850 rounded-2xl overflow-hidden shadow-xl hover:border-slate-800 transition"
                  >
                    <div className="flex items-center justify-between px-5 py-4 border-b border-slate-850 bg-slate-850/40">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-blue-500/15 text-blue-400 flex items-center justify-center">
                          <FolderTree size={18} />
                        </div>
                        <div>
                          <p className="text-white font-bold text-sm">{parent.name}</p>
                          <p className="text-xs text-slate-500 font-mono">/{parent.slug}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {renderMargin(parent)}
                        <button
                          onClick={() => handleDelete(parent.id, parent.name)}
                          className="p-2 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-900/20 transition cursor-pointer"
                          title="삭제"
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </div>

                    {children.length > 0 ? (
                      <div className="divide-y divide-slate-850">
                        {children.map((child) => (
                          <div
                            key={child.id}
                            className="flex items-center justify-between px-5 py-3 hover:bg-slate-800/20 transition"
                          >
                            <div className="flex items-center gap-2 text-sm">
                              <ChevronRight size={13} className="text-slate-650" />
                              <span className="text-slate-350">{child.name}</span>
                              <span className="text-xs text-slate-600 font-mono">/{child.slug}</span>
                            </div>
                            <div className="flex items-center gap-2">
                              {renderMargin(child)}
                              <button
                                onClick={() => handleDelete(child.id, child.name)}
                                className="p-1.5 rounded text-slate-600 hover:text-red-400 hover:bg-red-900/20 transition cursor-pointer"
                              >
                                <Trash2 size={13} />
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="px-5 py-4 text-xs text-slate-600 italic">
                        하위 카테고리 없음
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </>
      ) : (
        <>
          {/* 브랜드 관리 뷰 */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <h2 className="text-xl font-bold text-white mb-1 tracking-tight">수입 브랜드 설정 (Luxury Brands)</h2>
              <p className="text-slate-400 text-xs">
                쇼핑몰의 핵심 명품 브랜드를 등록·관리합니다. GNB 브랜드관 및 카테고리 교차 필터링에 실시간 연동됩니다. 총 <span className="text-white font-bold">{brands.length}</span>개
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => setShowBrandForm(!showBrandForm)}
                className={`px-4 py-2 rounded-lg flex items-center font-semibold text-sm transition-colors shadow-lg cursor-pointer ${
                  showBrandForm ? "bg-slate-700 text-slate-350" : "bg-blue-600 hover:bg-blue-500 text-white shadow-blue-900/30"
                }`}
              >
                {showBrandForm ? <X size={15} className="mr-1.5" /> : <Plus size={15} className="mr-1.5" />}
                {showBrandForm ? "닫기" : "새 브랜드 추가"}
              </button>
              <button
                onClick={fetchBrands}
                className="bg-slate-800 hover:bg-slate-700 text-white px-3 py-2 rounded-lg flex items-center text-sm transition-colors cursor-pointer"
              >
                <RefreshCw size={14} className={`mr-1.5 ${brandLoading ? "animate-spin text-blue-400" : ""}`} /> 새로고침
              </button>
            </div>
          </div>

          {/* 새 브랜드 추가 폼 */}
          {showBrandForm && (
            <div className="bg-slate-900 border border-blue-500/30 rounded-2xl p-6 shadow-xl shadow-blue-900/10">
              <h3 className="text-md font-bold text-white mb-4 flex items-center gap-2">
                <Plus size={18} className="text-blue-450" /> 새 수입 브랜드 등록
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs text-slate-400 font-medium mb-1.5">브랜드 한글명</label>
                  <input
                    type="text"
                    placeholder="예: 루이비통"
                    value={newBrandName}
                    onChange={(e) => setNewBrandName(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-white text-sm placeholder:text-slate-500 focus:outline-none focus:border-blue-500 transition"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-400 font-medium mb-1.5">브랜드 영문명 (대소문자 대조)</label>
                  <input
                    type="text"
                    placeholder="예: Louis Vuitton"
                    value={newBrandEngName}
                    onChange={(e) => setNewBrandEngName(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-white text-sm placeholder:text-slate-500 focus:outline-none focus:border-blue-500 transition"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-400 font-medium mb-1.5">슬러그 (영문소문자 & 대시)</label>
                  <input
                    type="text"
                    placeholder="예: louis-vuitton"
                    value={newBrandSlug}
                    onChange={(e) => setNewBrandSlug(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-white text-sm placeholder:text-slate-500 focus:outline-none focus:border-blue-500 transition"
                  />
                </div>
                <div className="sm:col-span-2">
                  <label className="block text-xs text-slate-400 font-medium mb-1.5">로고 이미지 URL (선택)</label>
                  <input
                    type="text"
                    placeholder="예: https://...logo.png"
                    value={newBrandLogo}
                    onChange={(e) => setNewBrandLogo(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-white text-sm placeholder:text-slate-500 focus:outline-none focus:border-blue-500 transition"
                  />
                </div>
                <div className="flex items-end pb-2.5">
                  <label className="flex items-center gap-2 text-sm text-slate-300 font-bold cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={newBrandPremium}
                      onChange={(e) => setNewBrandPremium(e.target.checked)}
                      className="w-4 h-4 rounded border-slate-700 text-blue-650 bg-slate-800 focus:ring-blue-600 focus:ring-offset-slate-900"
                    />
                    <span>인기 프리미엄 브랜드 지정</span>
                  </label>
                </div>
              </div>
              <div className="mt-5 flex justify-end">
                <button
                  onClick={handleCreateBrand}
                  disabled={brandSubmitting}
                  className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-2 rounded-xl font-bold text-sm transition disabled:opacity-50 shadow-lg cursor-pointer"
                >
                  {brandSubmitting ? "등록 중..." : "브랜드 등록"}
                </button>
              </div>
            </div>
          )}

          {/* 브랜드 목록 테이블 */}
          {brandLoading ? (
            <div className="flex flex-col items-center justify-center p-16 text-slate-550">
              <Loader2 size={36} className="animate-spin text-blue-500 mb-4" />
              <p className="text-sm">브랜드 사전을 조회하고 있습니다...</p>
            </div>
          ) : brands.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-16 bg-slate-900 border border-slate-850 rounded-2xl text-slate-500">
              <Sparkles size={48} className="mb-4 text-slate-700" />
              <h3 className="text-lg font-medium text-slate-400">등록된 수입 브랜드가 없습니다</h3>
              <p className="text-sm mt-2">우측 상단 "새 브랜드 추가" 버튼으로 브랜드관을 연동해보세요.</p>
            </div>
          ) : (
            <div className="bg-slate-900 border border-slate-850 rounded-2xl overflow-hidden shadow-2xl">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm text-slate-300">
                  <thead className="bg-slate-950 text-slate-400 font-bold text-xs uppercase border-b border-slate-850">
                    <tr>
                      <th className="px-6 py-4">브랜드명 (한글)</th>
                      <th className="px-6 py-4">브랜드명 (영문)</th>
                      <th className="px-6 py-4">슬러그 (URL 경로)</th>
                      <th className="px-6 py-4 text-center">프리미엄 노출</th>
                      <th className="px-6 py-4 text-center">활성화 여부</th>
                      <th className="px-6 py-4 text-right">관리</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-850">
                    {brands.map((b) => (
                      <tr key={b.id} className="hover:bg-slate-850/30 transition">
                        <td className="px-6 py-4 font-bold text-white flex items-center gap-3">
                          {b.logo_url ? (
                            <img src={b.logo_url} alt={b.name} className="w-8 h-8 object-contain bg-slate-800 rounded p-1" />
                          ) : (
                            <div className="w-8 h-8 rounded bg-slate-800 flex items-center justify-center text-xs font-mono font-black text-slate-500">
                              {b.eng_name.charAt(0)}
                            </div>
                          )}
                          <span>{b.name}</span>
                        </td>
                        <td className="px-6 py-4 font-semibold text-slate-400">{b.eng_name}</td>
                        <td className="px-6 py-4 font-mono text-xs">/brand/{b.slug}</td>
                        <td className="px-6 py-4 text-center">
                          <button
                            onClick={() => handleToggleBrandFlag(b, "is_premium")}
                            className="inline-flex items-center justify-center p-1 rounded-lg hover:bg-slate-800 transition cursor-pointer"
                            title="프리미엄 브랜드로 GNB 및 배너 우선 배치"
                          >
                            {b.is_premium ? (
                              <div className="px-2.5 py-1 text-[10px] font-bold text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-full flex items-center gap-1">
                                <Sparkles size={10} />
                                <span>PREMIUM</span>
                              </div>
                            ) : (
                              <div className="px-2.5 py-1 text-[10px] font-bold text-slate-550 border border-slate-800 rounded-full">
                                일반
                              </div>
                            )}
                          </button>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <button
                            onClick={() => handleToggleBrandFlag(b, "is_active")}
                            className="inline-flex items-center justify-center transition cursor-pointer"
                          >
                            {b.is_active ? (
                              <ToggleRight size={28} className="text-emerald-500" />
                            ) : (
                              <ToggleLeft size={28} className="text-slate-600" />
                            )}
                          </button>
                        </td>
                        <td className="px-6 py-4 text-right">
                          <button
                            onClick={() => handleDeleteBrand(b.id, b.name)}
                            className="p-2 rounded-lg text-slate-550 hover:text-red-400 hover:bg-red-950/20 transition cursor-pointer"
                            title="삭제"
                          >
                            <Trash2 size={15} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
