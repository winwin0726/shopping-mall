"use client";
import { authFetch } from "@/lib/api";

import React, { useEffect, useState } from "react";
import { Box, CheckCircle, XCircle, Loader2, AlertCircle, RefreshCw, Play, Send, X, Search, Filter, ExternalLink } from "lucide-react";
import Image from "next/image";

interface PendingProduct {
  id: number;
  originalName: string;
  name: string;
  price: number;
  margin: string;
  imageUrl: string | null;
}

interface CategoryOption {
  id: number;
  name: string;
  slug: string;
  parent_id: number | null;
}

interface Vendor {
  id: string;
  name: string;
  url: string;
  category: string;
  vendor_code: string;
}

export default function PipelineTab() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";
  const [products, setProducts] = useState<PendingProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [categories, setCategories] = useState<CategoryOption[]>([]);

  // 크롤러 컨트롤 상태
  const [showCrawlerPanel, setShowCrawlerPanel] = useState(false);
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [vendorsLoading, setVendorsLoading] = useState(false);
  const [activeCategory, setActiveCategory] = useState<string>("전체");
  const [searchTerm, setSearchTerm] = useState("");
  const [targetUrls, setTargetUrls] = useState(""); // 누락되었던 상태 변수 추가
  const [activeTab, setActiveTab] = useState<"vendors" | "direct">("vendors"); // 탭 선택 상태 추가

  // 수집 설정 모달 상태
  const [showScrapeModal, setShowScrapeModal] = useState(false);
  const [selectedVendor, setSelectedVendor] = useState<Vendor | null>(null);
  const [scrapeCount, setScrapeCount] = useState(5);
  const [scrapeCategoryId, setScrapeCategoryId] = useState("");
  const [exchangeRate, setExchangeRate] = useState(200.0);
  const [marginRate, setMarginRate] = useState(1.3);
  const [isCrawling, setIsCrawling] = useState(false);
  const [crawlStatus, setCrawlStatus] = useState<{type: "success"|"error", msg: string} | null>(null);

  // 승인 모달 상태
  const [showApproveModal, setShowApproveModal] = useState(false);
  const [selectedProductId, setSelectedProductId] = useState<number | null>(null);
  const [selectedCategoryId, setSelectedCategoryId] = useState<string>("");

  const fetchPendingProducts = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await authFetch(`${apiUrl}/api/admin/pending-products`);
      if (!res.ok) throw new Error("크롤러 수집 대기열을 불러오지 못했습니다.");
      const data = await res.json();
      setProducts(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchCategories = async () => {
    try {
      const res = await authFetch(`${apiUrl}/api/admin/categories`);
      if (res.ok) {
        const data = await res.json();
        setCategories(data);
      }
    } catch (err) {
      console.error("Categories fetch error:", err);
    }
  };

  const fetchVendors = async () => {
    setVendorsLoading(true);
    try {
      const res = await authFetch(`${apiUrl}/api/crawler/vendors`);
      if (res.ok) {
        const data = await res.json();
        setVendors(data);
      }
    } catch (err) {
      console.error("Vendors fetch error:", err);
    } finally {
      setVendorsLoading(false);
    }
  };

  useEffect(() => {
    fetchPendingProducts();
    fetchCategories();
    fetchVendors();
  }, []);

  const handleStatusUpdate = async (productId: number, newStatus: "APPROVED" | "REJECTED") => {
    const actionName = newStatus === "APPROVED" ? "승인" : "반려";
    if (!confirm(`스토어에 이 상품을 정말로 ${actionName}하시겠습니까?`)) return;

    try {
      const res = await authFetch(`${apiUrl}/api/admin/product/${productId}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus })
      });
      if (!res.ok) throw new Error(`상품 상태 변경 실패 (${res.status})`);
      
      // UI에서 해당 타일 즉시 제거
      setProducts((prev) => prev.filter((p) => p.id !== productId));
    } catch (err: any) {
      alert(err.message);
    }
  };

  const openApproveModal = (productId: number) => {
    setSelectedProductId(productId);
    setSelectedCategoryId("");
    setShowApproveModal(true);
  };

  const handleApproveConfirm = async () => {
    if (!selectedProductId) return;
    if (!selectedCategoryId) {
      alert("진열할 카테고리를 선택해 주세요.");
      return;
    }

    try {
      const res = await authFetch(`${apiUrl}/api/admin/product/${selectedProductId}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          status: "APPROVED",
          category_id: parseInt(selectedCategoryId)
        })
      });
      if (!res.ok) throw new Error(`진열 승인 실패 (${res.status})`);
      
      setProducts((prev) => prev.filter((p) => p.id !== selectedProductId));
      setShowApproveModal(false);
      alert("상품이 지정된 카테고리에 성공적으로 진열되었습니다!");
    } catch (err: any) {
      alert(err.message);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="flex justify-between items-center bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-xl">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 bg-blue-900/30 text-blue-500 rounded-xl flex items-center justify-center">
            <Box size={24} />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-white mb-1 tracking-tight">VTON 파이프라인 승인 대기소</h2>
            <p className="text-slate-400 text-sm">해외 도매 사이트에서 크롤링되어 AI 번역 및 피팅이 완료된 상품들입니다.</p>
          </div>
        </div>
        <div className="flex gap-3">
          <button 
            onClick={() => setShowCrawlerPanel(!showCrawlerPanel)}
            className="bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 px-5 py-2.5 rounded-lg flex items-center transition-colors shadow-lg font-medium border border-blue-500/30"
          >
            <Play size={18} className="mr-2" /> 새 수집 작업
          </button>
          <button 
            onClick={fetchPendingProducts} 
            className="bg-slate-800 hover:bg-slate-700 text-white px-5 py-2.5 rounded-lg flex items-center transition-colors shadow-lg font-medium"
          >
            <RefreshCw size={18} className={`mr-2 ${loading ? 'animate-spin text-blue-400' : ''}`} /> 새로고침
          </button>
        </div>
      </div>

      {/* 크롤링 트리거 제어판 */}
      {showCrawlerPanel && (
        <div className="bg-slate-900 border border-slate-800 p-6 rounded-2xl shadow-xl animate-in slide-in-from-top-4 duration-300 space-y-6">
          <div className="flex justify-between items-center border-b border-slate-850 pb-4">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <Send size={18} className="text-blue-500"/> 해외 도매처 상품 수집 봇 제어판
            </h3>
            {/* 탭 인터페이스 */}
            <div className="flex bg-slate-950 p-1 rounded-lg border border-slate-800">
              <button
                onClick={() => { setActiveTab("vendors"); setCrawlStatus(null); }}
                className={`px-4 py-1.5 rounded-md text-xs font-bold transition ${activeTab === "vendors" ? "bg-blue-600 text-white" : "text-slate-400 hover:text-white"}`}
              >
                스마트 업체 선택
              </button>
              <button
                onClick={() => { setActiveTab("direct"); setCrawlStatus(null); }}
                className={`px-4 py-1.5 rounded-md text-xs font-bold transition ${activeTab === "direct" ? "bg-blue-600 text-white" : "text-slate-400 hover:text-white"}`}
              >
                직접 주소 입력
              </button>
            </div>
          </div>

          {activeTab === "vendors" ? (
            <div className="space-y-4">
              <div className="flex flex-col sm:flex-row gap-3">
                {/* 검색 바 */}
                <div className="relative flex-1">
                  <Search size={16} className="absolute left-3.5 top-3.5 text-slate-500" />
                  <input
                    type="text"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    placeholder="업체명 또는 도매처 코드로 검색..."
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-10 pr-4 py-2.5 text-sm text-slate-300 placeholder-slate-600 focus:outline-none focus:border-blue-500 transition"
                  />
                </div>
                {/* 카테고리 필터 */}
                <div className="flex gap-1.5 overflow-x-auto pb-1 sm:pb-0">
                  {["전체", "의류", "가방", "신발", "악세사리"].map((cat) => (
                    <button
                      key={cat}
                      onClick={() => setActiveCategory(cat)}
                      className={`px-3 py-2 rounded-xl text-xs font-semibold whitespace-nowrap transition border ${
                        activeCategory === cat
                          ? "bg-blue-650 text-blue-400 border-blue-500/40 bg-blue-900/20"
                          : "bg-slate-950 text-slate-400 border-slate-850 hover:text-white"
                      }`}
                    >
                      {cat}
                    </button>
                  ))}
                </div>
              </div>

              {vendorsLoading ? (
                <div className="flex justify-center py-12">
                  <Loader2 size={36} className="animate-spin text-blue-500" />
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 max-h-[350px] overflow-y-auto pr-1">
                  {vendors
                    .filter(v => {
                      const matchesSearch = v.name.toLowerCase().includes(searchTerm.toLowerCase()) || (v.vendor_code && v.vendor_code.toLowerCase().includes(searchTerm.toLowerCase()));
                      const matchesCat = activeCategory === "전체" || v.category === activeCategory;
                      return matchesSearch && matchesCat;
                    })
                    .map((v) => (
                      <div
                        key={v.id}
                        onClick={() => {
                          setSelectedVendor(v);
                          setScrapeCategoryId("");
                          setCrawlStatus(null);
                          setShowScrapeModal(true);
                        }}
                        className="bg-slate-950 hover:bg-slate-850 border border-slate-850 hover:border-blue-500/40 p-4 rounded-xl cursor-pointer transition flex flex-col justify-between group"
                      >
                        <div>
                          <div className="flex justify-between items-start gap-2 mb-2">
                            <span className="px-2 py-0.5 bg-slate-800 text-slate-400 text-[10px] font-bold rounded-md uppercase tracking-wider">
                              {v.category}
                            </span>
                            <span className="text-xs text-slate-600 font-mono group-hover:text-blue-400 transition">
                              {v.vendor_code || "CODE-N/A"}
                            </span>
                          </div>
                          <h4 className="text-sm font-bold text-white mb-1 group-hover:text-blue-300 transition line-clamp-1">{v.name}</h4>
                        </div>
                        <div className="mt-3 flex items-center justify-between text-[11px] text-slate-500 pt-2 border-t border-slate-900">
                          <span className="line-clamp-1 max-w-[80%] hover:underline text-slate-600">
                            {v.url}
                          </span>
                          <ExternalLink size={12} className="opacity-0 group-hover:opacity-100 text-blue-400 transition-opacity" />
                        </div>
                      </div>
                    ))}
                  {vendors.filter(v => {
                    const matchesSearch = v.name.toLowerCase().includes(searchTerm.toLowerCase()) || (v.vendor_code && v.vendor_code.toLowerCase().includes(searchTerm.toLowerCase()));
                    const matchesCat = activeCategory === "전체" || v.category === activeCategory;
                    return matchesSearch && matchesCat;
                  }).length === 0 && (
                    <div className="col-span-full py-12 text-center text-slate-500 text-sm">
                      검색 조건에 부합하는 등록된 도매처가 없습니다.
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-4">
              <p className="text-slate-400 text-xs mb-2">Szwego 등 추출할 해외 벤더의 카탈로그 URL을 입력하세요. 여러 개일 경우 줄바꿈(엔터)으로 구분합니다.</p>
              <textarea
                value={targetUrls}
                onChange={(e) => setTargetUrls(e.target.value)}
                placeholder="https://szwego.com/album/example1&#10;https://szwego.com/album/example2"
                className="w-full h-32 bg-slate-950 border border-slate-800 rounded-xl p-4 text-slate-300 placeholder-slate-700 focus:outline-none focus:border-blue-500 resize-none font-mono text-sm mb-2"
              />

              {crawlStatus && (
                <div className={`p-3 rounded-lg text-sm mb-2 flex items-center gap-2 ${crawlStatus.type === 'success' ? 'bg-emerald-900/30 text-emerald-400 border border-emerald-800' : 'bg-red-900/30 text-red-400 border border-red-800'}`}>
                  {crawlStatus.type === 'success' ? <CheckCircle size={16}/> : <AlertCircle size={16}/>}
                  {crawlStatus.msg}
                </div>
              )}

              <div className="flex justify-end gap-3 pt-2">
                <button 
                  onClick={async () => {
                    const urls = targetUrls.split("\n").map(u => u.trim()).filter(u => u);
                    if (urls.length === 0) return setCrawlStatus({type: "error", msg: "최소 1개 이상의 URL을 입력해주세요."});
                    
                    setIsCrawling(true);
                    setCrawlStatus(null);
                    
                    try {
                      const res = await authFetch(`${apiUrl}/api/crawler/start`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                          target_urls: urls,
                          category_id: 1, // 직접 수집 시 임시 기본 카테고리 지정
                          exchange_rate: 200.0,
                          margin_rate: 1.3
                        })
                      });
                      if (!res.ok) throw new Error("API 요청 실패");
                      
                      const data = await res.json();
                      setCrawlStatus({type: "success", msg: data.message || "✅ 수집 작업이 성공적으로 백그라운드 큐에 등록되었습니다!"});
                      setTargetUrls("");
                      
                      setTimeout(fetchPendingProducts, 2000);
                      
                    } catch (e: any) {
                      setCrawlStatus({type: "error", msg: `오류 발생: ${e.message}`});
                    } finally {
                      setIsCrawling(false);
                    }
                  }}
                  disabled={isCrawling}
                  className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-2.5 rounded-xl flex items-center font-bold shadow-lg transition disabled:opacity-50 text-sm"
                >
                  {isCrawling ? <><Loader2 size={16} className="animate-spin mr-2"/> 수집 봇 파견 중...</> : <><Play size={16} className="mr-2"/> 백그라운드 봇 가동</>}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {error && (
        <div className="bg-red-900/40 border border-red-800 text-red-200 p-4 rounded-xl flex items-center shadow-lg">
          <AlertCircle className="mr-3 text-red-500" size={24} />
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex flex-col items-center justify-center p-24 text-slate-500">
          <Loader2 size={48} className="animate-spin text-blue-500 mb-4" />
          <p>크롤러 파이프라인 데이터베이스에서 읽어오는 중...</p>
        </div>
      ) : products.length === 0 ? (
        <div className="flex flex-col items-center justify-center p-24 bg-slate-900 border border-slate-800 rounded-2xl text-slate-500 shadow-xl">
          <CheckCircle size={64} className="mb-6 text-emerald-500/50" />
          <h3 className="text-xl font-bold text-emerald-400 mb-2">승인 대기 중인 상품이 없습니다</h3>
          <p className="text-sm text-center max-w-sm">AI 크롤러 봇이 수집한 모든 상품이 원활하게 본 매장으로 이출되었습니다.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {products.map((p) => (
            <div key={p.id} className="bg-slate-800/80 border border-slate-700 rounded-2xl overflow-hidden shadow-2xl flex flex-col transition hover:border-slate-600">
              <div className="relative aspect-[4/3] bg-slate-900 overflow-hidden">
                {p.imageUrl ? (
                  <img src={p.imageUrl} alt={p.name} className="w-full h-full object-cover transition-transform hover:scale-105" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-slate-600 font-bold bg-slate-950">
                    No VTON Image
                  </div>
                )}
                <div className="absolute top-3 left-3 px-3 py-1 bg-yellow-500 text-yellow-950 text-xs font-extrabold rounded-full shadow-lg flex items-center gap-1">
                   <AlertCircle size={14}/> 대기중
                </div>
              </div>
              
              <div className="p-5 flex-1 flex flex-col">
                <div className="mb-4">
                  <span className="text-xs text-slate-500 uppercase tracking-widest font-semibold block mb-1">AI Translation</span>
                  <h3 className="text-lg font-bold text-white line-clamp-2 leading-tight">{p.name}</h3>
                  <p className="text-sm text-slate-500 line-clamp-1 mt-1 font-serif italic text-ellipsis overflow-hidden" title={p.originalName}>{p.originalName}</p>
                </div>
                
                <div className="mt-auto grid grid-cols-2 gap-4 border-t border-slate-700 pt-4 mb-5">
                  <div>
                    <p className="text-xs text-slate-400 font-semibold mb-1">도매 원가</p>
                    <p className="text-base text-white font-mono font-bold">₩{p.price.toLocaleString()}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-400 font-semibold mb-1">예상 수익률</p>
                    <p className="text-base text-emerald-400 font-bold">{p.margin}</p>
                  </div>
                </div>

                <div className="flex gap-3">
                  <button 
                    onClick={() => handleStatusUpdate(p.id, "REJECTED")}
                    className="flex-1 flex items-center justify-center p-3 rounded-xl bg-slate-900 border border-slate-700 text-slate-400 hover:text-red-400 hover:bg-slate-955 transition font-bold text-sm shadow-md bg-slate-950"
                  >
                    <XCircle size={18} className="mr-2"/> 반려
                  </button>
                  <button 
                    onClick={() => openApproveModal(p.id)}
                    className="flex-1 flex items-center justify-center p-3 rounded-xl bg-blue-600 text-white hover:bg-blue-500 transition font-bold text-sm shadow-lg shadow-blue-900/30"
                  >
                    <CheckCircle size={18} className="mr-2"/> 쇼핑몰에 진열
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ═══ 카테고리 매핑 승인 팝업 모달 ═══ */}
      {showApproveModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
            
            {/* 헤더 */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800">
              <div>
                <h3 className="text-lg font-bold text-white">진열 카테고리 지정</h3>
                <p className="text-xs text-slate-500">상품을 등록할 카테고리를 선택해 주세요.</p>
              </div>
              <button 
                onClick={() => setShowApproveModal(false)} 
                className="p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition"
              >
                <X size={20} />
              </button>
            </div>

            {/* 본문 */}
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-semibold text-slate-300 mb-2">카테고리 선택 <span className="text-red-400">*</span></label>
                <select
                  value={selectedCategoryId} 
                  onChange={e => setSelectedCategoryId(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 text-white text-sm focus:outline-none focus:border-blue-500 transition"
                >
                  <option value="">카테고리를 골라주세요...</option>
                  {categories.filter(c => !c.parent_id).map(parent => (
                    <optgroup key={`group-${parent.id}`} label={parent.name} className="bg-slate-900 font-bold text-slate-400 italic">
                      <option value={parent.id} className="bg-slate-800 text-white font-normal not-italic px-2">
                        {parent.name} (전체)
                      </option>
                      {categories
                        .filter(child => child.parent_id === parent.id)
                        .map(child => (
                          <option key={child.id} value={child.id} className="bg-slate-800 text-white font-normal not-italic px-4">
                            &nbsp;&nbsp;ㄴ {child.name}
                          </option>
                        ))}
                    </optgroup>
                  ))}
                </select>
              </div>
            </div>

            {/* 푸터 */}
            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-slate-800 bg-slate-950">
              <button 
                onClick={() => setShowApproveModal(false)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-sm font-semibold transition"
              >
                취소
              </button>
              <button 
                onClick={handleApproveConfirm}
                className="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-bold shadow-lg shadow-blue-900/30 transition-colors"
              >
                진열 승인 완료
              </button>
            </div>

          </div>
        </div>
      )}

      {/* ═══ 스마트 업체 수집 설정 모달 ═══ */}
      {showScrapeModal && selectedVendor && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden">
            {/* 헤더 */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-850">
              <div>
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  <Play size={18} className="text-blue-500" /> 수집 봇 가동 설정
                </h3>
                <p className="text-xs text-slate-500">[{selectedVendor.name}] 도매처 상품을 백그라운드로 가져옵니다.</p>
              </div>
              <button
                onClick={() => { if (!isCrawling) setShowScrapeModal(false); }}
                className="p-2 rounded-lg hover:bg-slate-850 text-slate-400 hover:text-white transition"
                disabled={isCrawling}
              >
                <X size={20} />
              </button>
            </div>

            {/* 본문 */}
            <div className="p-6 space-y-4">
              <div className="bg-slate-950 border border-slate-850 p-4 rounded-xl space-y-1.5 text-xs text-slate-400">
                <div className="flex justify-between"><span className="font-semibold text-slate-500 font-sans">업체명:</span> <span className="text-slate-300 font-bold">{selectedVendor.name}</span></div>
                <div className="flex justify-between"><span className="font-semibold text-slate-500 font-sans">앨범주소:</span> <span className="text-slate-300 line-clamp-1 max-w-[280px] font-mono">{selectedVendor.url}</span></div>
                <div className="flex justify-between"><span className="font-semibold text-slate-500 font-sans">카테고리:</span> <span className="text-slate-300 font-semibold">{selectedVendor.category}</span></div>
              </div>

              {/* 1. 수집 수량 */}
              <div>
                <label className="block text-xs font-bold text-slate-400 mb-2 uppercase tracking-wide">수집할 상품 개수</label>
                <div className="grid grid-cols-4 gap-2">
                  {[1, 3, 5, 10].map((num) => (
                    <button
                      key={num}
                      type="button"
                      onClick={() => setScrapeCount(num)}
                      className={`py-2 rounded-xl text-xs font-bold border transition ${
                        scrapeCount === num
                          ? "bg-blue-650 text-blue-400 border-blue-500/40 bg-blue-900/20"
                          : "bg-slate-950 text-slate-400 border-slate-850 hover:text-white"
                      }`}
                    >
                      {num}개
                    </button>
                  ))}
                </div>
              </div>

              {/* 2. 쇼핑몰 진열 카테고리 */}
              <div>
                <label className="block text-xs font-bold text-slate-400 mb-2 uppercase tracking-wide">쇼핑몰 진열 대상 카테고리 <span className="text-red-500">*</span></label>
                <select
                  value={scrapeCategoryId}
                  onChange={(e) => setScrapeCategoryId(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-white text-xs focus:outline-none focus:border-blue-500 transition"
                >
                  <option value="">카테고리를 골라주세요...</option>
                  {categories.filter(c => !c.parent_id).map(parent => (
                    <optgroup key={`scrape-group-${parent.id}`} label={parent.name} className="bg-slate-900 font-bold text-slate-400 italic">
                      <option value={parent.id} className="bg-slate-850 text-white font-normal not-italic px-2">
                        {parent.name} (전체)
                      </option>
                      {categories
                        .filter(child => child.parent_id === parent.id)
                        .map(child => (
                          <option key={`scrape-${child.id}`} value={child.id} className="bg-slate-850 text-white font-normal not-italic px-4">
                            &nbsp;&nbsp;ㄴ {child.name}
                          </option>
                        ))}
                    </optgroup>
                  ))}
                </select>
              </div>

              {/* 3. 환율 및 마진율 */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-slate-400 mb-1.5 uppercase tracking-wide">원화 환율 ({"CNY -> KRW"})</label>
                  <input
                    type="number"
                    step="0.1"
                    value={exchangeRate}
                    onChange={(e) => setExchangeRate(parseFloat(e.target.value) || 0)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-white text-xs font-mono focus:outline-none focus:border-blue-500 transition"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-400 mb-1.5 uppercase tracking-wide">마진율 배수</label>
                  <input
                    type="number"
                    step="0.05"
                    value={marginRate}
                    onChange={(e) => setMarginRate(parseFloat(e.target.value) || 0)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-white text-xs font-mono focus:outline-none focus:border-blue-500 transition"
                  />
                </div>
              </div>

              {crawlStatus && (
                <div className={`p-4 rounded-xl text-xs flex items-start gap-2.5 ${crawlStatus.type === 'success' ? 'bg-emerald-950/40 text-emerald-400 border border-emerald-900/50' : 'bg-red-950/40 text-red-400 border border-red-900/50'}`}>
                  {crawlStatus.type === 'success' ? <CheckCircle size={16} className="mt-0.5 shrink-0" /> : <AlertCircle size={16} className="mt-0.5 shrink-0" />}
                  <div className="leading-relaxed font-semibold">{crawlStatus.msg}</div>
                </div>
              )}
            </div>

            {/* 푸터 */}
            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-slate-850 bg-slate-950">
              <button
                type="button"
                onClick={() => setShowScrapeModal(false)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-xs font-semibold transition"
                disabled={isCrawling}
              >
                취소
              </button>
              <button
                type="button"
                onClick={async () => {
                  if (!scrapeCategoryId) {
                    alert("진열할 카테고리를 지정해 주세요!");
                    return;
                  }
                  
                  setIsCrawling(true);
                  setCrawlStatus(null);

                  try {
                    const res = await authFetch(`${apiUrl}/api/crawler/scrape-platform`, {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({
                        platform: "weishang",
                        target_url: selectedVendor.url,
                        target_count: scrapeCount,
                        exchange_rate: exchangeRate,
                        margin_rate: marginRate,
                        category_id: parseInt(scrapeCategoryId)
                      })
                    });

                    const data = await res.json();
                    if (!res.ok) {
                      throw new Error(data.detail || "수집 봇 파견 요청에 실패했습니다.");
                    }

                    setCrawlStatus({
                      type: "success",
                      msg: `✅ 수집 봇이 성공적으로 백그라운드에 파견되었습니다! 잠시 후 대기소 목록을 새로고침(Refresh)해 주세요.`
                    });

                    setTimeout(() => {
                      setShowScrapeModal(false);
                      setCrawlStatus(null);
                      fetchPendingProducts();
                    }, 4000);

                  } catch (e: any) {
                    setCrawlStatus({ type: "error", msg: `오류: ${e.message}` });
                  } finally {
                    setIsCrawling(false);
                  }
                }}
                disabled={isCrawling}
                className="bg-blue-600 hover:bg-blue-500 text-white px-5 py-2 text-xs font-bold rounded-lg shadow-lg shadow-blue-900/30 transition disabled:opacity-50 flex items-center"
              >
                {isCrawling ? (
                  <>
                    <Loader2 size={14} className="animate-spin mr-1.5" />
                    수집 봇 가동 중...
                  </>
                ) : (
                  <>
                    <Play size={14} className="mr-1.5" />
                    수집 가동 시작
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
