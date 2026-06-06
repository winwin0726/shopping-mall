"use client";
import { authFetch, API_URL } from "@/lib/api";

import { useEffect, useState } from "react";
import {
  Tags, Plus, Trash2, Loader2, AlertCircle, RefreshCw,
  FolderTree, ChevronRight, X
} from "lucide-react";

interface Category {
  id: number;
  name: string;
  slug: string;
  parent_id: number | null;
  margin_type?: string;   // 'percent' | 'fixed' (윈윈 도킹: 도매가→소매가 마진)
  margin_value?: number;  // percent면 %, fixed면 원
}

export default function CategoriesTab() {
  const apiUrl = API_URL;
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 새 카테고리 입력
  const [showForm, setShowForm] = useState(false);
  const [newName, setNewName] = useState("");
  const [newSlug, setNewSlug] = useState("");
  const [newParentId, setNewParentId] = useState<number | "">("");
  const [submitting, setSubmitting] = useState(false);
  const [savingMargin, setSavingMargin] = useState<number | null>(null);  // 윈윈 도킹 마진 저장중

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

  useEffect(() => {
    fetchCategories();
  }, []);

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

  // [윈윈 도킹] 카테고리 마진 로컬 수정 + 저장
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

  // 카테고리별 마진 편집 컨트롤 (도매가 + 마진 = 소매가. %면 천원 올림)
  const renderMargin = (cat: Category) => (
    <div className="flex items-center gap-1 shrink-0" title="윈윈 도매가에 얹을 소매 마진 (%면 천원 단위 올림)">
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
        className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs px-2 py-1 rounded font-bold disabled:opacity-50"
      >
        {savingMargin === cat.id ? "..." : "저장"}
      </button>
    </div>
  );

  // 트리 구조 가공
  const topLevel = categories.filter((c) => !c.parent_id);
  const getChildren = (parentId: number) => categories.filter((c) => c.parent_id === parentId);

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* 헤더 */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-white mb-1 tracking-tight">카테고리 관리 (Categories)</h2>
          <p className="text-slate-400 text-sm">
            대분류/중분류 카테고리를 생성·관리하고, <span className="text-emerald-400 font-semibold">카테고리별 소매 마진</span>(윈윈 도매가 → 소매가)을 설정합니다. 총 <span className="text-white font-bold">{categories.length}</span>개
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowForm(!showForm)}
            className={`px-5 py-2.5 rounded-lg flex items-center font-medium transition-colors shadow-lg ${
              showForm ? "bg-slate-700 text-slate-300" : "bg-blue-600 hover:bg-blue-500 text-white shadow-blue-900/30"
            }`}
          >
            {showForm ? <X size={16} className="mr-2" /> : <Plus size={16} className="mr-2" />}
            {showForm ? "닫기" : "새 카테고리"}
          </button>
          <button
            onClick={fetchCategories}
            className="bg-slate-800 hover:bg-slate-700 text-white px-4 py-2.5 rounded-lg flex items-center transition-colors"
          >
            <RefreshCw size={16} className={`mr-2 ${loading ? "animate-spin text-blue-400" : ""}`} /> 새로고침
          </button>
        </div>
      </div>

      {/* 새 카테고리 폼 */}
      {showForm && (
        <div className="bg-slate-900 border border-blue-500/30 rounded-2xl p-6 shadow-xl shadow-blue-900/10">
          <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
            <Plus size={20} className="text-blue-400" /> 새 카테고리 추가
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs text-slate-400 font-medium mb-1.5">카테고리 이름</label>
              <input
                type="text"
                placeholder="예: 여성 의류"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-white text-sm placeholder:text-slate-500 focus:outline-none focus:border-blue-500 transition"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-400 font-medium mb-1.5">슬러그 (URL)</label>
              <input
                type="text"
                placeholder="예: women-clothing"
                value={newSlug}
                onChange={(e) => setNewSlug(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-white text-sm placeholder:text-slate-500 focus:outline-none focus:border-blue-500 transition"
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
              className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-2.5 rounded-xl font-bold text-sm transition disabled:opacity-50 shadow-lg shadow-blue-900/30"
            >
              {submitting ? "생성 중..." : "카테고리 생성"}
            </button>
          </div>
        </div>
      )}

      {error && (
        <div className="bg-red-900/40 border border-red-800 text-red-200 p-4 rounded-xl flex items-center">
          <AlertCircle className="mr-3 text-red-500" size={24} />
          {error}
        </div>
      )}

      {/* 카테고리 트리 */}
      {loading ? (
        <div className="flex flex-col items-center justify-center p-16 text-slate-500">
          <Loader2 size={40} className="animate-spin text-blue-500 mb-4" />
          <p>카테고리 로딩 중...</p>
        </div>
      ) : categories.length === 0 ? (
        <div className="flex flex-col items-center justify-center p-16 bg-slate-900 border border-slate-800 rounded-2xl text-slate-500">
          <Tags size={48} className="mb-4 text-slate-700" />
          <h3 className="text-lg font-medium text-slate-400">등록된 카테고리가 없습니다</h3>
          <p className="text-sm mt-2">위의 "새 카테고리" 버튼으로 첫 카테고리를 생성해보세요.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {topLevel.map((parent) => {
            const children = getChildren(parent.id);
            return (
              <div
                key={parent.id}
                className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-xl hover:border-slate-700 transition"
              >
                {/* 대분류 헤더 */}
                <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800 bg-slate-800/40">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-blue-500/15 text-blue-400 flex items-center justify-center">
                      <FolderTree size={20} />
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
                      className="p-2 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-900/20 transition"
                      title="삭제"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>

                {/* 하위 카테고리 리스트 */}
                {children.length > 0 ? (
                  <div className="divide-y divide-slate-800">
                    {children.map((child) => (
                      <div
                        key={child.id}
                        className="flex items-center justify-between px-5 py-3 hover:bg-slate-800/30 transition"
                      >
                        <div className="flex items-center gap-2 text-sm">
                          <ChevronRight size={14} className="text-slate-600" />
                          <span className="text-slate-300">{child.name}</span>
                          <span className="text-xs text-slate-600 font-mono">/{child.slug}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          {renderMargin(child)}
                          <button
                            onClick={() => handleDelete(child.id, child.name)}
                            className="p-1.5 rounded text-slate-600 hover:text-red-400 hover:bg-red-900/20 transition"
                          >
                            <Trash2 size={14} />
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

          {/* 상위 없는 고아 카테고리 */}
          {categories
            .filter((c) => c.parent_id && !categories.find((p) => p.id === c.parent_id))
            .map((orphan) => (
              <div
                key={orphan.id}
                className="bg-slate-900 border border-amber-500/20 rounded-2xl px-5 py-4 flex items-center justify-between shadow-xl"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-amber-500/15 text-amber-400 flex items-center justify-center">
                    <Tags size={18} />
                  </div>
                  <div>
                    <p className="text-white font-bold text-sm">{orphan.name}</p>
                    <p className="text-xs text-amber-400">부모 카테고리 누락</p>
                  </div>
                </div>
                <button
                  onClick={() => handleDelete(orphan.id, orphan.name)}
                  className="p-2 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-900/20 transition"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            ))}
        </div>
      )}
    </div>
  );
}
