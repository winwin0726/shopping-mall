"use client";
import { authFetch, API_URL } from "@/lib/api";

import { useEffect, useState, useCallback, useRef } from "react";
import dynamic from "next/dynamic";
import {
  Package, Search, Trash2, Loader2, AlertCircle, RefreshCw,
  ChevronLeft, ChevronRight, Filter, Eye, Edit3, X, Check, Plus, Upload,
  ImagePlus, Star, GripVertical, Link2, Camera, Cpu, Settings, Copy, Play
} from "lucide-react";


interface Product {
  id: number;
  kr_name: string;
  cn_name: string | null;
  base_price: number;
  sale_price: number | null;
  discount_rate: number | null;
  stock_quantity: number;
  sku: string | null;
  category_id: number;
  category_name: string | null;
  status: string;
  ai_fitting_image_url: string | null;
  transparent_item_image_url: string | null;
  images: string[] | null;
  video_url: string | null;
  kr_description: string | null;
  description_html: string | null;
  size_stock_config: any;
  keywords: string[] | null;
  created_at: string | null;
}

interface CategoryOption {
  id: number;
  name: string;
  slug: string;
  parent_id: number | null;
}

interface NewProductForm {
  kr_name: string;
  cn_name: string;
  base_price: string;
  sale_price: string;
  discount_rate: string;
  stock_quantity: string;
  category_id: string;
  kr_description: string;
  description_html: string;
  sku: string;
  ai_fitting_image_url: string;
  transparent_item_image_url: string;
  images: string[];
  video_url: string;
  tag_string: string;
  size_stock_config: string;
}

const emptyForm: NewProductForm = {
  kr_name: "", cn_name: "", base_price: "", sale_price: "",
  discount_rate: "", stock_quantity: "0", category_id: "", kr_description: "",
  description_html: "",
  sku: "", ai_fitting_image_url: "", transparent_item_image_url: "", images: [], video_url: "",
  tag_string: "",
  size_stock_config: "",
};

const extractSizesFromText = (text: string, categoryName: string): Record<string, number> => {
  if (!text) return {};
  const textUpper = text.toUpperCase();
  const sizes: Record<string, number> = {};
  const categoryNameLower = categoryName.toLowerCase();

  // 의류 카테고리
  if (["의류", "상의", "하의", "아우터", "패션", "mens-clothing", "clothing"].some(k => categoryNameLower.includes(k))) {
    const clothingPatterns = ["XS", "S", "M", "L", "XL", "XXL", "XXXL", "FREE"];
    clothingPatterns.forEach(size => {
      const escapedSize = size.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&');
      const regex = new RegExp(`\\b${escapedSize}\\b`, 'i');
      if (
        regex.test(textUpper) || 
        textUpper.includes(` ${size} `) || 
        textUpper.includes(`-${size}`) || 
        textUpper.includes(`/${size}`)
      ) {
        sizes[size] = 99;
      }
    });
  }
  // 신발 카테고리
  else if (["신발", "슈즈", "스니커즈", "shoes"].some(k => categoryNameLower.includes(k))) {
    const shoeSizes = ["220", "225", "230", "235", "240", "245", "250", "255", "260", "265", "270", "275", "280", "285", "290"];
    shoeSizes.forEach(size => {
      if (textUpper.includes(size)) {
        sizes[size] = 99;
      }
    });
  }
  // 가방 카테고리
  else if (["가방", "백", "핸드백", "bags"].some(k => categoryNameLower.includes(k))) {
    const bagSizes = ["MINI", "MEDIUM", "LARGE", "FREE"];
    bagSizes.forEach(size => {
      const escapedSize = size.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&');
      const regex = new RegExp(`\\b${escapedSize}\\b`, 'i');
      if (regex.test(textUpper)) {
        const formatted = size !== "FREE" ? size.charAt(0) + size.slice(1).toLowerCase() : "Free";
        sizes[formatted] = 99;
      }
    });
  }

  return sizes;
};

const formatDate = (dateStr: string | null): string => {
  if (!dateStr) return "-";
  try {
    const cleanStr = dateStr.replace('T', ' ');
    const datePart = cleanStr.split(' ')[0]; // "2026-06-02"
    if (datePart.length === 10) {
      return datePart.substring(2); // "26-06-02"
    }
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    const yy = String(d.getFullYear()).substring(2);
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    return `${yy}-${mm}-${dd}`;
  } catch (e) {
    return dateStr;
  }
};

/* ─────────── 이미지 업로더 컴포넌트 (드래그앤드롭 정렬 탑재) ─────────── */
function SmartImageUploader({
  images,
  onImagesChange,
  mainImageUrl,
  onMainImageUrlChange,
}: {
  images: string[];
  onImagesChange: (imgs: string[]) => void;
  mainImageUrl: string;
  onMainImageUrlChange: (url: string) => void;
}) {
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [showUrlInput, setShowUrlInput] = useState(false);
  const [urlInputValue, setUrlInputValue] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 이미지 드래그앤드롭 순서 변경용 상태
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  // 확대보기(라이트박스) 상태
  const [enlargedUrl, setEnlargedUrl] = useState<string | null>(null);

  const uploadFiles = async (files: FileList | File[]) => {
    const imageFiles = Array.from(files).filter(f => f.type.startsWith("image/"));
    if (imageFiles.length === 0) return;
    if (images.length + imageFiles.length > 30) {
      alert("최대 30장까지 업로드 가능합니다.");
      return;
    }

    setUploading(true);
    try {
      const formData = new FormData();
      imageFiles.forEach(f => formData.append("files", f));

      const res = await authFetch(`${API_URL}/api/admin/upload/multiple`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) throw new Error("업로드 실패");
      const data = await res.json();

      const newUrls = data.uploaded.map((u: any) => u.url);
      const updatedImages = [...images, ...newUrls];
      onImagesChange(updatedImages);

      // 첫 번째 이미지를 대표 이미지로 자동 설정
      if (!mainImageUrl && updatedImages.length > 0) {
        onMainImageUrlChange(updatedImages[0]);
      }

      if (data.errors?.length > 0) {
        alert(`${data.errors.length}개 파일 업로드 실패: ${data.errors.map((e: any) => e.filename).join(", ")}`);
      }
    } catch (err: any) {
      alert(err.message);
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files.length > 0) {
      uploadFiles(e.dataTransfer.files);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      uploadFiles(e.target.files);
    }
    e.target.value = "";
  };

  const removeImage = (index: number) => {
    const updated = images.filter((_, i) => i !== index);
    onImagesChange(updated);
    if (images[index] === mainImageUrl) {
      onMainImageUrlChange(updated[0] || "");
    }
  };

  const setAsMain = (url: string) => {
    onMainImageUrlChange(url);
  };

  const addUrlImage = () => {
    const url = urlInputValue.trim();
    if (!url) return;
    if (!url.startsWith("http")) {
      alert("올바른 URL을 입력하세요 (http:// 또는 https://)");
      return;
    }
    if (images.length >= 30) {
      alert("최대 30장까지 등록 가능합니다.");
      return;
    }
    const updated = [...images, url];
    onImagesChange(updated);
    if (!mainImageUrl) onMainImageUrlChange(url);
    setUrlInputValue("");
    setShowUrlInput(false);
  };

  // 이미지 드래그앤드롭 핸들러
  const handleImgDragStart = (index: number) => {
    setDraggedIndex(index);
  };

  const handleImgDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault();
  };

  const handleImgDrop = (index: number) => {
    if (draggedIndex === null || draggedIndex === index) return;
    const updated = [...images];
    const draggedItem = updated[draggedIndex];
    updated.splice(draggedIndex, 1);
    updated.splice(index, 0, draggedItem);
    onImagesChange(updated);
    setDraggedIndex(null);
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label className="block text-sm font-semibold text-slate-300">
          <Camera size={14} className="inline mr-1.5 -mt-0.5" />
          상품 이미지 <span className="text-slate-500 font-normal">({images.length}/30)</span>
          <span className="text-[10px] text-blue-400 block mt-0.5 font-normal">* 이미지를 드래그하여 노출 순서를 변경할 수 있습니다.</span>
        </label>
        <button
          type="button"
          onClick={() => setShowUrlInput(!showUrlInput)}
          className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1 transition"
        >
          <Link2 size={12} />
          {showUrlInput ? "닫기" : "URL로 추가"}
        </button>
      </div>

      {/* URL 직접 입력 */}
      {showUrlInput && (
        <div className="flex gap-2 animate-in slide-in-from-top-2 duration-200">
          <input
            type="text"
            placeholder="https://example.com/image.jpg"
            value={urlInputValue}
            onChange={e => setUrlInputValue(e.target.value)}
            onKeyDown={e => e.key === "Enter" && addUrlImage()}
            className="flex-1 bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm placeholder:text-slate-500 focus:outline-none focus:border-blue-500 transition"
          />
          <button
            type="button"
            onClick={addUrlImage}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-medium transition shrink-0"
          >
            추가
          </button>
        </div>
      )}

      {/* 드래그앤드롭 영역 */}
      <div
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => !uploading && fileInputRef.current?.click()}
        className={`relative border-2 border-dashed rounded-xl transition-all cursor-pointer
          ${dragOver
            ? "border-blue-400 bg-blue-500/10 scale-[1.01]"
            : "border-slate-700 hover:border-slate-500 bg-slate-800/50 hover:bg-slate-800"
          }
          ${images.length > 0 ? "p-3" : "p-8"}
        `}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          multiple
          onChange={handleFileSelect}
          className="hidden"
        />

        {/* 업로드 중 오버레이 */}
        {uploading && (
          <div className="absolute inset-0 bg-slate-900/80 backdrop-blur-sm rounded-xl flex items-center justify-center z-10">
            <div className="flex flex-col items-center gap-2">
              <Loader2 size={32} className="animate-spin text-blue-400" />
              <span className="text-sm text-blue-300 font-medium">업로드 중...</span>
            </div>
          </div>
        )}

        {images.length === 0 ? (
          <div className="flex flex-col items-center gap-3 text-slate-500">
            <div className="w-16 h-16 rounded-2xl bg-slate-700/50 flex items-center justify-center">
              <ImagePlus size={28} className="text-slate-500" />
            </div>
            <div className="text-center">
              <p className="text-sm font-medium text-slate-400">이미지를 드래그하거나 클릭하여 업로드</p>
              <p className="text-xs text-slate-600 mt-1">JPG, PNG, WebP · 최대 30장</p>
            </div>
          </div>
        ) : (
          /* 이미지 그리드 (DnD 구현) */
          <div className="grid grid-cols-4 sm:grid-cols-5 gap-2" onClick={e => e.stopPropagation()}>
            {images.map((url, i) => (
              <div
                key={`${url}-${i}`}
                draggable
                onDragStart={() => handleImgDragStart(i)}
                onDragOver={e => handleImgDragOver(e, i)}
                onDrop={() => handleImgDrop(i)}
                className={`relative group aspect-square rounded-lg overflow-hidden border-2 transition-all duration-300 cursor-grab active:cursor-grabbing transform hover:scale-[1.04] active:scale-[0.98]
                  ${url === mainImageUrl
                    ? "border-yellow-400 shadow-lg shadow-yellow-500/10"
                    : "border-slate-700 hover:border-slate-500"
                  }
                  ${draggedIndex === i ? "opacity-35 scale-90 border-blue-500" : "opacity-100"}
                `}
              >
                <img
                  src={url}
                  alt={`상품 이미지 ${i + 1}`}
                  className="w-full h-full object-cover pointer-events-none"
                  onError={e => { (e.target as HTMLImageElement).src = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect fill='%231e293b' width='100' height='100'/%3E%3Ctext x='50' y='55' text-anchor='middle' fill='%23475569' font-size='12'%3EError%3C/text%3E%3C/svg%3E"; }}
                />

                <div className="absolute top-1 right-1 opacity-0 group-hover:opacity-100 transition-opacity bg-black/60 p-0.5 rounded cursor-grab">
                  <GripVertical size={10} className="text-white" />
                </div>

                {/* 대표 이미지 뱃지 */}
                {url === mainImageUrl && (
                  <div className="absolute top-1 left-1 bg-yellow-500 text-yellow-950 rounded px-1.5 py-0.5 text-[9px] font-bold flex items-center gap-0.5 shadow">
                    <Star size={8} fill="currentColor" /> 대표
                  </div>
                )}

                {/* 순서 번호 */}
                <div className="absolute bottom-1 left-1 bg-black/60 text-white rounded px-1.5 py-0.5 text-[9px] font-bold z-10 pointer-events-none">
                  {i + 1}
                </div>

                {/* 호버 컨트롤 */}
                <div className="absolute inset-0 bg-black/70 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-1 z-10">
                  <button
                    type="button"
                    onClick={() => setEnlargedUrl(url)}
                    className="p-1.5 bg-slate-200 hover:bg-white text-slate-900 rounded transition transform hover:scale-110 active:scale-95"
                    title="확대보기"
                  >
                    <Eye size={11} />
                  </button>
                  {url !== mainImageUrl && (
                    <button
                      type="button"
                      onClick={() => setAsMain(url)}
                      className="p-1.5 bg-yellow-500 hover:bg-yellow-400 text-yellow-950 rounded transition transform hover:scale-110 active:scale-95"
                      title="대표 이미지로 설정"
                    >
                      <Star size={11} />
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => removeImage(i)}
                    className="p-1.5 bg-red-600 hover:bg-red-500 text-white rounded transition transform hover:scale-110 active:scale-95"
                    title="삭제"
                  >
                    <Trash2 size={11} />
                  </button>
                </div>
              </div>
            ))}

            {/* 추가 버튼 */}
            {images.length < 30 && (
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="aspect-square rounded-lg border-2 border-dashed border-slate-700 hover:border-blue-500 bg-slate-800/50 hover:bg-slate-800 flex flex-col items-center justify-center gap-1 transition text-slate-500 hover:text-blue-400"
              >
                <Plus size={20} />
                <span className="text-[10px] font-medium">추가</span>
              </button>
            )}
          </div>
        )}
      </div>

      {/* 확대보기 라이트박스 */}
      {enlargedUrl && (
        <div
          className="fixed inset-0 z-[100] bg-black/85 flex items-center justify-center p-6 cursor-zoom-out animate-in fade-in duration-150"
          onClick={() => setEnlargedUrl(null)}
        >
          <button
            type="button"
            onClick={() => setEnlargedUrl(null)}
            className="absolute top-4 right-4 p-2 bg-white/10 hover:bg-white/20 text-white rounded-full transition"
            title="닫기"
          >
            <X size={22} />
          </button>
          <img
            src={enlargedUrl}
            alt="확대 이미지"
            className="max-w-[92vw] max-h-[88vh] object-contain rounded-lg shadow-2xl"
            onClick={e => e.stopPropagation()}
          />
        </div>
      )}
    </div>
  );
}

const RichEditor = dynamic(() => import("./RichEditor"), { ssr: false });

/* ─────────── 메인 ProductsTab 컴포넌트 ─────────── */
export default function ProductsTab() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [page, setPage] = useState(1);
  const perPage = 15;

  // 인라인 편집
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editPrice, setEditPrice] = useState("");
  const [editStock, setEditStock] = useState("");

  // 신규 상품 등록 모달
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createForm, setCreateForm] = useState<NewProductForm>({ ...emptyForm });
  const [creating, setCreating] = useState(false);
  const [vtonUploading, setVtonUploading] = useState(false);
  const [categories, setCategories] = useState<CategoryOption[]>([]);
  const [isEditMode, setIsEditMode] = useState(false);

  const vtonFileInputRef = useRef<HTMLInputElement>(null);

  const handleVtonUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      if (!file.type.startsWith("image/")) {
        alert("이미지 파일만 업로드 가능합니다.");
        return;
      }
      setVtonUploading(true);
      try {
        const formData = new FormData();
        formData.append("file", file);
        const res = await authFetch(`${API_URL}/api/admin/upload/`, {
          method: "POST",
          body: formData,
        });
        if (!res.ok) throw new Error("업로드 실패");
        const data = await res.json();
        setCreateForm(f => ({ ...f, transparent_item_image_url: data.url }));
      } catch (err: any) {
        alert(err.message);
      } finally {
        setVtonUploading(false);
        e.target.value = "";
      }
    }
  };

  // [수동 누끼 가공] 상태 관리 및 가공용 핸들러 추가
  const [isExtractingTransparent, setIsExtractingTransparent] = useState(false);
  const [selectedExtractImage, setSelectedExtractImage] = useState("");

  const handleExtractTransparent = async () => {
    if (!editingId) return;
    if (!selectedExtractImage) {
      alert("누끼 가공을 수행할 이미지를 선택해 주세요.");
      return;
    }
    
    setIsExtractingTransparent(true);
    try {
      const res = await authFetch(`${API_URL}/api/admin/product/${editingId}/extract-transparent`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image_url: selectedExtractImage }),
      });
      
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "누끼 가공 중 오류가 발생했습니다.");
      }
      
      setCreateForm(f => ({ ...f, transparent_item_image_url: data.transparent_item_image_url }));
      alert("AI 누끼 가공이 완료되었습니다.");
    } catch (err: any) {
      alert(`누끼 가공 실패: ${err.message}`);
    } finally {
      setIsExtractingTransparent(false);
    }
  };

  // 대표동영상 직접 업로드 관련 상태
  const [videoMode, setVideoMode] = useState<"upload" | "url">("url");
  const [videoUploading, setVideoUploading] = useState(false);
  const videoFileInputRef = useRef<HTMLInputElement>(null);

  const handleVideoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      if (!file.type.startsWith("video/")) {
        alert("동영상 파일만 업로드 가능합니다.");
        return;
      }
      setVideoUploading(true);
      try {
        const formData = new FormData();
        formData.append("file", file);
        const res = await authFetch(`${API_URL}/api/admin/upload/`, {
          method: "POST",
          body: formData,
        });
        if (!res.ok) throw new Error("업로드 실패");
        const data = await res.json();
        setCreateForm(f => ({ ...f, video_url: data.url }));
      } catch (err: any) {
        alert(err.message);
      } finally {
        setVideoUploading(false);
        e.target.value = "";
      }
    }
  };

  // 상세 옵션별 재고 관련 상태
  const [optionStocks, setOptionStocks] = useState<Record<string, number>>({});
  const [customOptionVal, setCustomOptionVal] = useState("");

  const handleOptionStockChange = (key: string, val: string) => {
    const num = parseInt(val) || 0;
    const updated = { ...optionStocks, [key]: num };
    setOptionStocks(updated);
    
    // 전체 수량 합산 계산
    const total = Object.values(updated).reduce((acc, curr) => acc + curr, 0);
    setCreateForm(f => ({
      ...f,
      size_stock_config: JSON.stringify(updated),
      stock_quantity: String(total)
    }));
  };

  const handleCategoryChange = (catId: string) => {
    setCreateForm(f => ({ ...f, category_id: catId }));
    if (!catId) {
      setOptionStocks({});
      return;
    }
    const cat = categories.find(c => String(c.id) === catId);
    const catName = cat ? cat.name : "";
    
    // 비어있을 때만 카테고리 템플릿 기본값 로드
    if (Object.keys(optionStocks).length === 0) {
      let template: Record<string, number> = {};
      if (catName.includes("의류") || catName.includes("아우터") || catName.includes("상의") || catName.includes("하의")) {
        template = { "S": 0, "M": 0, "L": 0, "XL": 0, "Free": 0 };
      } else if (catName.includes("가방") || catName.includes("백")) {
        template = { "Mini": 0, "Medium": 0, "Large": 0, "Free": 0 };
      } else if (catName.includes("신발") || catName.includes("슈즈")) {
        template = { "230": 0, "235": 0, "240": 0, "245": 0, "250": 0, "255": 0, "260": 0, "265": 0, "270": 0, "275": 0, "280": 0 };
      }
      setOptionStocks(template);
      setCreateForm(f => ({
        ...f,
        size_stock_config: JSON.stringify(template),
        stock_quantity: "0"
      }));
    }
  };

  const addCustomOptionKey = () => {
    const key = customOptionVal.trim();
    if (!key) return;
    if (optionStocks[key] !== undefined) {
      alert("이미 존재하는 옵션 규격입니다.");
      return;
    }
    const updated = { ...optionStocks, [key]: 0 };
    setOptionStocks(updated);
    setCreateForm(f => ({ ...f, size_stock_config: JSON.stringify(updated) }));
    setCustomOptionVal("");
  };

  const removeOptionKey = (key: string) => {
    const updated = { ...optionStocks };
    delete updated[key];
    setOptionStocks(updated);
    const total = Object.values(updated).reduce((acc, curr) => acc + curr, 0);
    setCreateForm(f => ({
      ...f,
      size_stock_config: JSON.stringify(updated),
      stock_quantity: String(total)
    }));
  };

  // 가격-할인율 양방향 반응형 계산 연동 핸들러
  const handleBasePriceChange = (val: string) => {
    const bp = parseInt(val) || 0;
    setCreateForm(f => {
      let sp = f.sale_price;
      let dr = f.discount_rate;
      if (bp > 0) {
        if (f.discount_rate) {
          sp = String(Math.round(bp * (1 - (parseInt(f.discount_rate) || 0) / 100)));
        } else if (f.sale_price) {
          dr = String(Math.round((1 - (parseInt(f.sale_price) || 0) / bp) * 100));
        }
      }
      return { ...f, base_price: val, sale_price: sp, discount_rate: dr };
    });
  };

  const handleSalePriceChange = (val: string) => {
    const sp = parseInt(val) || 0;
    setCreateForm(f => {
      const bp = parseInt(f.base_price) || 0;
      let dr = f.discount_rate;
      if (bp > 0 && sp > 0) {
        dr = String(Math.round((1 - sp / bp) * 100));
      }
      return { ...f, sale_price: val, discount_rate: dr };
    });
  };

  const handleDiscountRateChange = (val: string) => {
    const dr = parseInt(val) || 0;
    setCreateForm(f => {
      const bp = parseInt(f.base_price) || 0;
      let sp = f.sale_price;
      if (bp > 0) {
        sp = String(Math.round(bp * (1 - dr / 100)));
      }
      return { ...f, discount_rate: val, sale_price: sp };
    });
  };

  // 윈윈크롤러3 연동 설정 상태
  const [crawlerEnabled, setCrawlerEnabled] = useState(true);
  const [exchangeRate, setExchangeRate] = useState("200.0");
  const [marginRate, setMarginRate] = useState("1.3");
  const [securityToken, setSecurityToken] = useState("LUXAI-WINWIN-TOKEN-1234");
  const [saveCrawlerLoading, setSaveCrawlerLoading] = useState(false);
  const [wechatLoginLoading, setWechatLoginLoading] = useState(false);
  const [scrapePlatform, setScrapePlatform] = useState("weishang");
  const [scrapeUrl, setScrapeUrl] = useState("");
  const [scrapeCount, setScrapeCount] = useState(1);
  const [scrapeLoading, setScrapeLoading] = useState(false);
  const [showCrawlerPanel, setShowCrawlerPanel] = useState(false);

  // 크롤러 시뮬레이터 테스터용
  const [crawlerRawJson, setCrawlerRawJson] = useState("");
  const [crawlerTestLoading, setCrawlerTestLoading] = useState(false);
  const [crawlerTestResult, setCrawlerTestResult] = useState<any>(null);

  // AI 자동 정보 생성 상태
  const [autofilling, setAutofilling] = useState(false);

  // 카테고리 목록 fetch
  useEffect(() => {
    authFetch(`${API_URL}/api/admin/categories`)
      .then(r => r.ok ? r.json() : [])
      .then(setCategories)
      .catch(() => {});

    // 크롤러 연동 설정 로드
    authFetch(`${API_URL}/api/crawler/settings`)
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data) {
          setCrawlerEnabled(data.enabled);
          setExchangeRate(String(data.exchangeRate));
          setMarginRate(String(data.marginRate));
          setSecurityToken(data.securityToken);
        }
      })
      .catch(() => {});
  }, []);

  const fetchProducts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      let url = `${API_URL}/api/admin/products?`;
      if (statusFilter) url += `status=${statusFilter}&`;
      if (searchTerm) url += `search=${encodeURIComponent(searchTerm)}&`;

      const res = await authFetch(url);
      if (!res.ok) throw new Error("상품 목록을 불러올 수 없습니다.");
      const data = await res.json();
      setProducts(data);
      setPage(1);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, searchTerm]);

  useEffect(() => {
    fetchProducts();
  }, [fetchProducts]);

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`정말로 "${name}" 상품을 삭제하시겠습니까? 이 동작은 되돌릴 수 없습니다.`)) return;
    try {
      const res = await authFetch(`${API_URL}/api/admin/product/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error("삭제 실패");
      setProducts((prev) => prev.filter((p) => p.id !== id));
    } catch (err: any) {
      alert(err.message);
    }
  };

  const startEdit = (p: Product) => {
    setIsEditMode(true);
    setEditingId(p.id);
    setCreateForm({
      kr_name: p.kr_name || "",
      cn_name: p.cn_name || "",
      base_price: String(p.base_price || ""),
      sale_price: String(p.sale_price || ""),
      discount_rate: String(p.discount_rate || ""),
      stock_quantity: String(p.stock_quantity || "0"),
      category_id: String(p.category_id || ""),
      kr_description: p.kr_description || "",
      description_html: p.description_html || "",
      sku: p.sku || "",
      ai_fitting_image_url: p.ai_fitting_image_url || "",
      transparent_item_image_url: p.transparent_item_image_url || "",
      images: p.images || [],
      video_url: p.video_url || "",
      tag_string: p.keywords ? p.keywords.join(", ") : "",
      size_stock_config: p.size_stock_config ? (typeof p.size_stock_config === "string" ? p.size_stock_config : JSON.stringify(p.size_stock_config)) : "",
    });

    // 수동 AI 누끼 작업 대상 이미지 초기화 (대표 이미지 우선, 없으면 첫번째 갤러리 이미지)
    const defaultExtractImage = p.ai_fitting_image_url || (p.images && p.images.length > 0 ? p.images[0] : "");
    setSelectedExtractImage(defaultExtractImage);
    setIsExtractingTransparent(false);

    // 상세 옵션 재고 복원
    let initialOptions: Record<string, number> = {};
    if (p.size_stock_config) {
      try {
        const parsed = typeof p.size_stock_config === "string" ? JSON.parse(p.size_stock_config) : p.size_stock_config;
        if (parsed && typeof parsed === "object") {
          initialOptions = parsed;
        }
      } catch {}
    }
    setOptionStocks(initialOptions);
    
    // 대표동영상 등록 모드 복원
    if (p.video_url && !p.video_url.includes("/uploads/")) {
      setVideoMode("url");
    } else if (p.video_url) {
      setVideoMode("upload");
    }

    setShowCreateModal(true);
  };

  const cancelEdit = () => {
    setEditingId(null);
  };

  const saveEdit = async (id: number) => {
    try {
      const res = await authFetch(`${API_URL}/api/admin/product/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sale_price: parseInt(editPrice) || 0,
          stock_quantity: parseInt(editStock) || 0,
        }),
      });
      if (!res.ok) throw new Error("수정 실패");
      setEditingId(null);
      fetchProducts();
    } catch (err: any) {
      alert(err.message);
    }
  };

  // 크롤러 설정 저장
  const handleSaveCrawlerSettings = async () => {
    setSaveCrawlerLoading(true);
    try {
      const res = await authFetch(`${API_URL}/api/crawler/settings`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          enabled: crawlerEnabled,
          exchangeRate: parseFloat(exchangeRate) || 200.0,
          marginRate: parseFloat(marginRate) || 1.3,
          securityToken: securityToken
        })
      });
      if (!res.ok) throw new Error("설정 저장 실패");
      alert("윈윈크롤러3 연동 설정이 성공적으로 저장되었습니다!");
    } catch (err: any) {
      alert(err.message);
    } finally {
      setSaveCrawlerLoading(false);
    }
  };

  // 위챗 QR 로그인 연동 제어
  const handleWeChatQRLogin = async () => {
    if (!confirm("백엔드 서버 화면에 위챗 QR 로그인 전용 크롬 창이 생성됩니다. 계속 진행하시겠습니까?")) return;
    setWechatLoginLoading(true);
    try {
      const res = await authFetch(`${API_URL}/api/crawler/wechat-qr-login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ headless: false })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "위챗 QR 로그인 세션 획득에 실패했습니다.");
      alert("🎉 위챗 로그인이 성공적으로 완료되어 크롤러 세션 정보가 저장되었습니다!");
    } catch (err: any) {
      alert(err.message);
    } finally {
      setWechatLoginLoading(false);
    }
  };

  // 3대 플랫폼 스마트 실시간 단일 수집 연동 실행 (폼 자동 도킹 기능 탑재)
  const handlePlatformScrape = async () => {
    if (!scrapeUrl.trim()) {
      alert("수집할 대상 URL 주소를 입력하세요.");
      return;
    }
    if (!createForm.category_id) {
      alert("카테고리를 먼저 선택한 후에 스크랩을 시작해 주세요. (사이즈 규격을 자동 매칭하기 위해 필수적입니다)");
      return;
    }
    setScrapeLoading(true);
    try {
      const res = await authFetch(`${API_URL}/api/crawler/scrape-direct`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target_url: scrapeUrl.trim(),
          category_id: parseInt(createForm.category_id),
          exchange_rate: parseFloat(exchangeRate) || 200.0,
          margin_rate: parseFloat(marginRate) || 1.3
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "실시간 수집 실행에 실패했습니다.");
      
      // 수집된 데이터를 입력 폼에 다이렉트로 채워넣기 (Auto-fill 도킹)
      const mapped = data.mapped_data;
      const catName = data.category_name || "";
      const parsedSizes = data.parsed_sizes || {};
      
      let finalOptionStocks: Record<string, number> = {};
      if (Object.keys(parsedSizes).length > 0) {
        finalOptionStocks = parsedSizes;
      } else if (catName) {
        if (catName.includes("의류") || catName.includes("아우터") || catName.includes("상의") || catName.includes("하의")) {
          finalOptionStocks = { "S": 99, "M": 99, "L": 99, "XL": 99, "Free": 99 };
        } else if (catName.includes("가방") || catName.includes("백")) {
          finalOptionStocks = { "Mini": 99, "Medium": 99, "Large": 99, "Free": 99 };
        } else if (catName.includes("신발") || catName.includes("슈즈")) {
          finalOptionStocks = { "230": 99, "235": 99, "240": 99, "245": 99, "250": 99, "255": 99, "260": 99, "265": 99, "270": 99, "275": 99, "280": 99 };
        }
      }
      
      setOptionStocks(finalOptionStocks);
      const totalStock = Object.values(finalOptionStocks).reduce((acc, curr) => acc + curr, 0);

      let descHtml = "";
      if (mapped.kr_description) {
        descHtml = mapped.kr_description
          .split('\n')
          .map((line: string) => `<p>${line}</p>`)
          .join('');
      }

      setCreateForm({
        category_id: mapped.category_id ? String(mapped.category_id) : createForm.category_id,
        cn_name: createForm.cn_name || mapped.kr_name,
        kr_name: mapped.kr_name || "",
        kr_description: mapped.kr_description || "",
        description_html: descHtml,
        base_price: String(data.calculated_price || 30000),
        sale_price: "",
        discount_rate: "",
        stock_quantity: String(totalStock),
        sku: createForm.sku || `LUX-${Math.floor(1000 + Math.random() * 9000)}`,
        images: mapped.images && mapped.images.length > 0 ? mapped.images : [data.original_image],
        ai_fitting_image_url: mapped.images && mapped.images.length > 0 ? mapped.images[0] : data.original_image,
        transparent_item_image_url: "", // 누끼는 수동 가공 또는 업로드
        video_url: mapped.video_url || "",
        size_stock_config: JSON.stringify(finalOptionStocks),
        tag_string: ""
      });

      alert("🎉 스마트 실시간 수집 성공! 한글화된 상품명, 가격, 자동 재고 매트릭스가 현재 등록 폼에 자동으로 채워졌습니다. 이미지를 검토하신 후 등록을 마무리하세요!");
    } catch (err: any) {
      alert(err.message);
    } finally {
      setScrapeLoading(false);
    }
  };

  // 크롤러 데이터 AI 가상 매핑 테스터
  const handleTestCrawlerMapping = async () => {
    if (!crawlerRawJson.trim()) {
      alert("테스트할 원본 크롤러 JSON을 입력하세요.");
      return;
    }
    setCrawlerTestLoading(true);
    setCrawlerTestResult(null);
    try {
      const res = await authFetch(`${API_URL}/api/crawler/test-mapping`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raw_json: crawlerRawJson })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "AI 파싱 분석에 실패했습니다.");
      setCrawlerTestResult(data);
    } catch (err: any) {
      alert(err.message);
    } finally {
      setCrawlerTestLoading(false);
    }
  };

  const handleApplyCrawlerData = () => {
    if (!crawlerTestResult) return;
    
    const mapped = crawlerTestResult.mapped_data;
    const catName = crawlerTestResult.category_name || "";
    const parsedSizes = crawlerTestResult.parsed_sizes || {};
    
    let finalOptionStocks: Record<string, number> = {};
    if (Object.keys(parsedSizes).length > 0) {
      finalOptionStocks = parsedSizes;
    } else if (catName) {
      if (catName.includes("의류") || catName.includes("아우터") || catName.includes("상의") || catName.includes("하의")) {
        finalOptionStocks = { "S": 99, "M": 99, "L": 99, "XL": 99, "Free": 99 };
      } else if (catName.includes("가방") || catName.includes("백")) {
        finalOptionStocks = { "Mini": 99, "Medium": 99, "Large": 99, "Free": 99 };
      } else if (catName.includes("신발") || catName.includes("슈즈")) {
        finalOptionStocks = { "230": 99, "235": 99, "240": 99, "245": 99, "250": 99, "255": 99, "260": 99, "265": 99, "270": 99, "275": 99, "280": 99 };
      }
    }
    
    setOptionStocks(finalOptionStocks);
    const total = Object.values(finalOptionStocks).reduce((acc, curr) => acc + curr, 0);

    let descHtml = "";
    if (mapped.kr_description) {
      descHtml = mapped.kr_description
        .split('\n')
        .map((line: string) => `<p>${line}</p>`)
        .join('');
    }
    
    let cnName = "";
    try {
      const rawObj = JSON.parse(crawlerRawJson);
      cnName = rawObj.goodsName || rawObj.title || "";
    } catch (e) {}

    setCreateForm({
      category_id: mapped.category_id ? String(mapped.category_id) : "1",
      cn_name: cnName,
      kr_name: mapped.kr_name || "",
      kr_description: mapped.kr_description || "",
      description_html: descHtml,
      base_price: String(crawlerTestResult.calculated_price || 30000),
      sale_price: "",
      discount_rate: "",
      stock_quantity: String(total),
      size_stock_config: JSON.stringify(finalOptionStocks),
      images: mapped.images || [],
      ai_fitting_image_url: mapped.images && mapped.images.length > 0 ? mapped.images[0] : "",
      transparent_item_image_url: "",
      tag_string: "",
      video_url: mapped.video_url || "",
      sku: ""
    });
    
    alert("크롤링 데이터 및 AI 사이즈 매칭 결과가 등록 폼에 성공적으로 적용되었습니다!");
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    alert("연동 웹훅 주소가 클립보드에 복사되었습니다!");
  };

  // AI 자동 정보 생성 및 채우기
  const handleAIAutofill = async () => {
    if (!createForm.kr_name && !createForm.cn_name) {
      alert("상품명(한국어) 또는 원문 상품명을 입력한 상태에서 실행해 주세요.");
      return;
    }
    setAutofilling(true);
    try {
      const res = await authFetch(`${API_URL}/api/admin/ai/product-autofill`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          kr_name: createForm.kr_name,
          cn_name: createForm.cn_name,
          category_id: createForm.category_id ? parseInt(createForm.category_id) : undefined,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => null);
        throw new Error(errData?.detail || "AI 자동 완성 요청에 실패했습니다.");
      }

      const data = await res.json();
      
      const targetCategoryId = data.category_id ? String(data.category_id) : createForm.category_id;
      const cat = categories.find(c => String(c.id) === targetCategoryId);
      const catName = cat ? cat.name : "";
      
      const textToParse = `${data.kr_name || createForm.kr_name || ""} ${data.kr_description || ""}`;
      const parsedSizes = extractSizesFromText(textToParse, catName);
      
      let finalOptionStocks: Record<string, number> = {};
      if (Object.keys(parsedSizes).length > 0) {
        finalOptionStocks = parsedSizes;
      } else if (catName) {
        if (catName.includes("의류") || catName.includes("아우터") || catName.includes("상의") || catName.includes("하의")) {
          finalOptionStocks = { "S": 99, "M": 99, "L": 99, "XL": 99, "Free": 99 };
        } else if (catName.includes("가방") || catName.includes("백")) {
          finalOptionStocks = { "Mini": 99, "Medium": 99, "Large": 99, "Free": 99 };
        } else if (catName.includes("신발") || catName.includes("슈즈")) {
          finalOptionStocks = { "230": 99, "235": 99, "240": 99, "245": 99, "250": 99, "255": 99, "260": 99, "265": 99, "270": 99, "275": 99, "280": 99 };
        }
      }

      if (Object.keys(finalOptionStocks).length > 0) {
        setOptionStocks(finalOptionStocks);
        const total = Object.values(finalOptionStocks).reduce((acc, curr) => acc + curr, 0);
        
        let descHtml = "";
        const descText = data.kr_description || createForm.kr_description || "";
        if (descText) {
          descHtml = descText
            .split('\n')
            .map((line: string) => `<p>${line}</p>`)
            .join('');
        }

        setCreateForm(prev => ({
          ...prev,
          kr_name: data.kr_name || prev.kr_name,
          kr_description: data.kr_description || prev.kr_description,
          description_html: descHtml || prev.description_html,
          category_id: targetCategoryId,
          base_price: prev.base_price || (data.recommended_price ? String(data.recommended_price) : prev.base_price),
          size_stock_config: JSON.stringify(finalOptionStocks),
          stock_quantity: String(total)
        }));
      } else {
        let descHtml = "";
        const descText = data.kr_description || createForm.kr_description || "";
        if (descText) {
          descHtml = descText
            .split('\n')
            .map((line: string) => `<p>${line}</p>`)
            .join('');
        }

        setCreateForm(prev => ({
          ...prev,
          kr_name: data.kr_name || prev.kr_name,
          kr_description: data.kr_description || prev.kr_description,
          description_html: descHtml || prev.description_html,
          category_id: targetCategoryId,
          base_price: prev.base_price || (data.recommended_price ? String(data.recommended_price) : prev.base_price),
        }));
      }

    } catch (err: any) {
      alert(err.message);
    } finally {
      setAutofilling(false);
    }
  };

  // 상품 등록/수정 제출
  const handleCreateProduct = async () => {
    setCreating(true);
    try {
      const body: any = {
        kr_name: createForm.kr_name,
        base_price: parseInt(createForm.base_price) || 0,
        category_id: parseInt(createForm.category_id),
        stock_quantity: parseInt(createForm.stock_quantity) || 0,
        transparent_item_image_url: createForm.transparent_item_image_url || null,
        description_html: createForm.description_html || null,
        video_url: createForm.video_url || null,
      };
      if (createForm.cn_name) body.cn_name = createForm.cn_name;
      if (createForm.sale_price) body.sale_price = parseInt(createForm.sale_price) || null;
      if (createForm.discount_rate) body.discount_rate = parseInt(createForm.discount_rate) || null;
      if (createForm.sku) body.sku = createForm.sku;
      if (createForm.kr_description) body.kr_description = createForm.kr_description;

      // size_stock_config 파싱
      if (createForm.size_stock_config) {
        try {
          body.size_stock_config = JSON.parse(createForm.size_stock_config);
        } catch {
          body.size_stock_config = null;
        }
      } else {
        body.size_stock_config = null;
      }

      // 태그 파싱 (쉼표 구분)
      if (createForm.tag_string.trim()) {
        body.keywords = createForm.tag_string.split(",").map(k => k.trim()).filter(Boolean);
      } else {
        body.keywords = [];
      }

      // 이미지 처리
      if (createForm.images.length > 0) {
        body.images = createForm.images;
        body.ai_fitting_image_url = createForm.ai_fitting_image_url || createForm.images[0];
      } else {
        body.images = [];
        body.ai_fitting_image_url = createForm.ai_fitting_image_url || null;
      }

      let res;
      if (isEditMode) {
        // 상품 정보 수정 요청
        res = await authFetch(`${API_URL}/api/admin/product/${editingId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      } else {
        // 신규 상품 등록 요청
        res = await authFetch(`${API_URL}/api/admin/product`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      }

      if (!res.ok) {
        const errData = await res.json().catch(() => null);
        throw new Error(errData?.detail || "처리에 실패했습니다.");
      }

      setShowCreateModal(false);
      setIsEditMode(false);
      setEditingId(null);
      setCreateForm({ ...emptyForm });
      setOptionStocks({});
      fetchProducts();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setCreating(false);
    }
  };

  // 페이지네이션
  const totalPages = Math.ceil(products.length / perPage);
  const paged = products.slice((page - 1) * perPage, page * perPage);

  const statusBadge = (status: string) => {
    const map: Record<string, { bg: string; text: string }> = {
      APPROVED: { bg: "bg-emerald-500/15 border-emerald-500/30", text: "text-emerald-400" },
      PENDING: { bg: "bg-yellow-500/15 border-yellow-500/30", text: "text-yellow-400" },
      REJECTED: { bg: "bg-red-500/15 border-red-500/30", text: "text-red-400" },
    };
    const s = map[status] || { bg: "bg-slate-700", text: "text-slate-300" };
    return (
      <span className={`px-2 py-0.5 rounded-full text-xs font-bold border ${s.bg} ${s.text}`}>
        {status}
      </span>
    );
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* 헤더 */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-white mb-1 tracking-tight">상품 관리 (Products)</h2>
          <p className="text-slate-400 text-sm">매장에 등록된 전체 상품을 조회·수정·삭제합니다. 총 <span className="text-white font-bold">{products.length}</span>개</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => { setCreateForm({ ...emptyForm }); setOptionStocks({}); setIsEditMode(false); setEditingId(null); setShowCreateModal(true); }}
            className="bg-blue-600 hover:bg-blue-500 text-white px-5 py-2.5 rounded-lg flex items-center transition-colors shadow-lg font-medium shrink-0"
          >
            <Plus size={16} className="mr-2" /> 새 상품 등록
          </button>
          <button
            onClick={() => setShowCrawlerPanel(!showCrawlerPanel)}
            className="bg-slate-800 hover:bg-slate-750 text-slate-300 hover:text-white px-5 py-2.5 rounded-lg flex items-center transition-colors shadow-lg font-medium shrink-0"
          >
            <Settings size={16} className="mr-2" /> 크롤러 연동 설정
          </button>
          <button
            onClick={fetchProducts}
            className="bg-slate-800 hover:bg-slate-700 text-white px-5 py-2.5 rounded-lg flex items-center transition-colors shadow-lg font-medium shrink-0"
          >
            <RefreshCw size={16} className={`mr-2 ${loading ? "animate-spin text-blue-400" : ""}`} /> 새로고침
          </button>
        </div>
      </div>

      {/* 윈윈크롤러3 연동 판넬 */}
      {showCrawlerPanel && (
        <div className="bg-slate-900 border border-slate-750 rounded-2xl p-6 space-y-6 animate-in slide-in-from-top-2 duration-300">
          <div className="border-b border-slate-800 pb-3 flex justify-between items-center">
            <div>
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Settings size={16} className="text-blue-500" /> 윈윈크롤러3 AI 연동 웹훅 게이트웨이 (Crawler Integration)
              </h3>
              <p className="text-[11px] text-slate-500 mt-0.5">타오바오, 1688 크롤러와 연계하여 상품 등록 프로세스를 자동화합니다.</p>
            </div>
            <button onClick={() => setShowCrawlerPanel(false)} className="text-slate-500 hover:text-white transition">
              <X size={16} />
            </button>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* 설정창 */}
            <div className="lg:col-span-5 space-y-4 border-r border-slate-850 pr-0 lg:pr-6">
              <div className="flex items-center justify-between bg-slate-950 p-3 rounded-lg border border-slate-850">
                <span className="text-xs font-bold text-slate-400">자동 크롤링 연동 활성화</span>
                <input
                  type="checkbox"
                  checked={crawlerEnabled}
                  onChange={e => setCrawlerEnabled(e.target.checked)}
                  className="w-4 h-4 rounded text-blue-600 bg-slate-800 border-slate-700 focus:ring-blue-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <span className="text-[10px] text-slate-500 block mb-1">고정 환율 설정 (CNY ➔ KRW)</span>
                  <input
                    type="text"
                    value={exchangeRate}
                    onChange={e => setExchangeRate(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-blue-600 transition"
                  />
                </div>
                <div>
                  <span className="text-[10px] text-slate-500 block mb-1">해외 소싱 마진율 (배수 곱)</span>
                  <input
                    type="text"
                    value={marginRate}
                    onChange={e => setMarginRate(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-blue-600 transition"
                  />
                </div>
              </div>

              <div>
                <span className="text-[10px] text-slate-500 block mb-1">크롤러 통신 보안용 API 토큰 (Security Token)</span>
                <input 
                  type="text" 
                  value={securityToken}
                  onChange={e => setSecurityToken(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1.5 text-xs font-mono text-white focus:outline-none focus:border-blue-600 transition" 
                />
              </div>

              <button
                onClick={handleSaveCrawlerSettings}
                disabled={saveCrawlerLoading}
                className="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-2 rounded-lg text-xs transition"
              >
                {saveCrawlerLoading ? "저장 중..." : "연동 설정 적용하기"}
              </button>

              <div className="pt-3 border-t border-slate-850 space-y-2">
                <span className="text-[10px] text-slate-500 block mb-1">🔑 윈윈크롤러3 세션 로그인 관리</span>
                <button
                  type="button"
                  onClick={handleWeChatQRLogin}
                  disabled={wechatLoginLoading}
                  className="w-full bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold py-2.5 rounded-lg text-xs transition flex justify-center items-center gap-1.5 shadow-md shadow-emerald-950/20 disabled:opacity-40"
                >
                  {wechatLoginLoading ? (
                    <>
                      <Loader2 size={12} className="animate-spin" />
                      위챗 QR 스캔 대기 중 (최대 3분)...
                    </>
                  ) : (
                    <>
                      <Cpu size={12} />
                      위챗(WeChat) QR 로그인 세션 동기화
                    </>
                  )}
                </button>
                <p className="text-[9px] text-slate-600 leading-normal">
                  * 웨이상 상품 수집을 위해 최초 1회 또는 세션 만료 시 QR 로그인이 필요합니다.
                </p>
              </div>
            </div>

            {/* 시뮬레이터 테스터 */}
            <div className="lg:col-span-7 space-y-4 bg-slate-950/40 p-4 rounded-xl border border-slate-850 flex flex-col">
              <h4 className="text-xs font-bold text-slate-300 flex items-center gap-1.5">
                <Cpu size={14} className="text-purple-400" /> AI 매핑 가상 시뮬레이터 (Simulator)
              </h4>
              
              <div className="flex-1 space-y-3">
                <div className="space-y-1">
                  <span className="text-[10px] text-slate-500 block">타오바오 / 1688 크롤러 원본 JSON 데이터 입력</span>
                  <textarea
                    rows={4}
                    value={crawlerRawJson}
                    onChange={e => setCrawlerRawJson(e.target.value)}
                    placeholder='{ "goodsName": "2026 夏季新款韩版简约气质连衣裙", "price": "129.50", "images": ["https://images.unsplash.com/photo-1595777457583-95e059d581b8"] }'
                    className="w-full bg-slate-900 border border-slate-800 rounded-lg p-2.5 text-xs text-white placeholder-slate-700 font-mono focus:outline-none focus:border-purple-600 transition resize-none leading-relaxed"
                  />
                </div>

                <button
                  type="button"
                  onClick={handleTestCrawlerMapping}
                  disabled={crawlerTestLoading}
                  className="w-full bg-purple-600 hover:bg-purple-500 text-white font-bold py-2 rounded-lg text-xs transition flex justify-center items-center gap-1.5"
                >
                  {crawlerTestLoading ? (
                    <>
                      <Loader2 size={12} className="animate-spin" />
                      Gemini 2.5 Flash AI가 해석하는 중...
                    </>
                  ) : (
                    <>
                      <Cpu size={12} />
                      AI 연동 가상 매핑 테스트 실행
                    </>
                  )}
                </button>
              </div>

              {/* 시뮬레이터 결과 노출 */}
              {crawlerTestResult && (
                <div className="bg-slate-900 border border-slate-800 rounded-lg p-3 space-y-2 text-xs animate-in fade-in duration-200">
                  <div className="text-[10px] font-bold text-purple-400 border-b border-slate-800 pb-1.5 flex justify-between">
                    <span>✨ AI 데이터 해석 및 스키마 변환 성공</span>
                    <span>가상 매핑 결과</span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-[11px]">
                    <div>
                      <span className="text-slate-500">한글화 상품명:</span>{" "}
                      <span className="text-white font-bold block truncate">{crawlerTestResult.mapped_data.kr_name}</span>
                    </div>
                    <div>
                      <span className="text-slate-500">분류된 카테고리:</span>{" "}
                      <span className="text-white block">{crawlerTestResult.category_name} (ID: {crawlerTestResult.mapped_data.category_id})</span>
                    </div>
                    <div>
                      <span className="text-slate-500">외화 원가:</span>{" "}
                      <span className="text-white block font-mono">{crawlerTestResult.mapped_data.base_price_foreign} (CNY/USD)</span>
                    </div>
                    <div>
                      <span className="text-slate-500">환산 판매가 (환율*마진):</span>{" "}
                      <span className="text-emerald-400 font-bold block font-mono">₩{crawlerTestResult.calculated_price.toLocaleString()}</span>
                    </div>
                  </div>
                  {crawlerTestResult.mapped_data.video_url && (
                    <div className="text-[10px] text-blue-400 truncate">
                      🎥 연동 동영상 추출 완료: {crawlerTestResult.mapped_data.video_url}
                    </div>
                  )}
                  
                  {/* AI 감지 사이즈 옵션 노출 */}
                  <div className="pt-1.5 border-t border-slate-800 space-y-1">
                    <span className="text-slate-500 block text-[10px]">🔎 AI 감지 사이즈 옵션 (기본 99개):</span>
                    {Object.keys(crawlerTestResult.parsed_sizes || {}).length > 0 ? (
                      <div className="flex flex-wrap gap-1">
                        {Object.entries(crawlerTestResult.parsed_sizes).map(([size, qty]) => (
                          <span key={size} className="px-2 py-0.5 bg-purple-950/80 border border-purple-800/60 rounded text-[10px] text-purple-300 font-semibold font-mono">
                            {size}: {String(qty)}개
                          </span>
                        ))}
                      </div>
                    ) : (
                      <span className="text-slate-500 block italic text-[10px]">사이즈 감지 없음 (카테고리 기본 사이즈런 99개씩 매칭 예정)</span>
                    )}
                  </div>

                  {/* 폼 적용 버튼 */}
                  <div className="pt-2">
                    <button
                      type="button"
                      onClick={handleApplyCrawlerData}
                      className="w-full bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold py-2 rounded-lg text-xs transition flex justify-center items-center gap-1 shadow-md shadow-emerald-950/30"
                    >
                      📥 이 데이터로 상품 등록 폼 채우기 (사이즈 99개 자동 적용)
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 필터 바 */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            placeholder="상품명 검색..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && fetchProducts()}
            className="w-full bg-slate-900 border border-slate-700 rounded-xl pl-10 pr-4 py-2.5 text-white text-sm placeholder:text-slate-500 focus:outline-none focus:border-blue-500 transition"
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter size={16} className="text-slate-500" />
          {["", "APPROVED", "PENDING", "REJECTED"].map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-3 py-2 rounded-lg text-xs font-bold transition ${
                statusFilter === s
                  ? "bg-blue-600 text-white shadow-lg shadow-blue-900/30"
                  : "bg-slate-800 text-slate-400 hover:text-white hover:bg-slate-750"
              }`}
            >
              {s || "전체"}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="bg-red-900/40 border border-red-800 text-red-200 p-4 rounded-xl flex items-center">
          <AlertCircle className="mr-3 text-red-500" size={24} />
          {error}
        </div>
      )}

      {/* 테이블 */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-slate-800/60 border-b border-slate-700">
                <th className="px-5 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">ID</th>
                <th className="px-5 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">이미지</th>
                <th className="px-5 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">상품명</th>
                <th className="px-5 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">카테고리</th>
                <th className="px-5 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">판매가</th>
                <th className="px-5 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">재고</th>
                <th className="px-5 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">상태</th>
                <th className="px-5 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">업데이트 날짜</th>
                <th className="px-5 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider text-right">관리</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {loading ? (
                <tr>
                  <td colSpan={9} className="p-12 text-center text-slate-500">
                    <Loader2 size={32} className="animate-spin text-blue-400 mx-auto mb-2" />
                    로딩 중...
                  </td>
                </tr>
              ) : paged.length === 0 ? (
                <tr>
                  <td colSpan={9} className="p-12 text-center text-slate-500">
                    <Package size={40} className="mx-auto mb-3 text-slate-700" />
                    등록된 상품이 없습니다.
                  </td>
                </tr>
              ) : (
                paged.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="px-5 py-3 text-sm text-slate-500">#{p.id}</td>
                    <td className="px-5 py-3">
                      {p.ai_fitting_image_url ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={p.ai_fitting_image_url}
                          alt={p.kr_name}
                          className="w-10 h-10 object-cover rounded-lg border border-slate-700"
                        />
                      ) : (
                        <div className="w-10 h-10 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-500">
                          <Package size={16} />
                        </div>
                      )}
                    </td>
                    <td className="px-5 py-3 font-semibold text-slate-200">{p.kr_name}</td>
                    <td className="px-5 py-3 text-slate-400">{p.category_name || "미지정"}</td>
                    <td className="px-5 py-3">
                      {editingId === p.id ? (
                        <input
                          type="number"
                          value={editPrice}
                          onChange={(e) => setEditPrice(e.target.value)}
                          className="w-24 bg-slate-800 border border-slate-700 rounded px-2 py-1 text-sm text-white focus:outline-none focus:border-blue-500 text-center"
                        />
                      ) : (
                        <div 
                          className="cursor-pointer hover:text-blue-400 transition"
                          onClick={() => {
                            setEditingId(p.id);
                            setEditPrice(String(p.sale_price || p.base_price));
                            setEditStock(String(p.stock_quantity));
                          }}
                          title="클릭하여 빠른 가격 수정"
                        >
                          {p.sale_price ? (
                            <>
                              <div className="text-emerald-400 font-bold text-sm">₩{p.sale_price.toLocaleString()}</div>
                              <div className="text-slate-500 text-[10px] line-through">₩{p.base_price.toLocaleString()}</div>
                            </>
                          ) : (
                            <div className="text-slate-200 font-bold text-sm">₩{p.base_price.toLocaleString()}</div>
                          )}
                        </div>
                      )}
                    </td>
                    <td className="px-5 py-3">
                      {editingId === p.id ? (
                        <input
                          type="number"
                          value={editStock}
                          onChange={(e) => setEditStock(e.target.value)}
                          className="w-20 bg-slate-800 border border-slate-700 rounded px-2 py-1 text-sm text-white focus:outline-none focus:border-blue-500 text-center"
                        />
                      ) : (
                        <span 
                          className={`text-sm font-medium cursor-pointer hover:text-blue-400 transition ${
                            p.stock_quantity <= 0 ? "text-red-400 font-bold" : "text-slate-350"
                          }`}
                          onClick={() => {
                            setEditingId(p.id);
                            setEditPrice(String(p.sale_price || p.base_price));
                            setEditStock(String(p.stock_quantity));
                          }}
                          title="클릭하여 빠른 재고 수정"
                        >
                          {p.stock_quantity}개
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-3">{statusBadge(p.status)}</td>
                    <td className="px-5 py-3 text-slate-400 text-xs font-mono">{formatDate(p.created_at)}</td>
                    <td className="px-5 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        {editingId === p.id ? (
                          <>
                            <button
                              onClick={() => saveEdit(p.id)}
                              className="p-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white transition"
                              title="저장"
                            >
                              <Check size={14} />
                            </button>
                            <button
                              onClick={cancelEdit}
                              className="p-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-white transition"
                              title="취소"
                            >
                              <X size={14} />
                            </button>
                          </>
                        ) : (
                          <>
                            <button
                              onClick={() => startEdit(p)}
                              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-750 text-slate-400 hover:text-white transition"
                              title="수정"
                            >
                              <Edit3 size={14} />
                            </button>
                            <button
                              onClick={() => handleDelete(p.id, p.kr_name)}
                              className="p-1.5 rounded-lg bg-slate-800 hover:bg-red-900/50 text-slate-400 hover:text-red-400 transition"
                              title="삭제"
                            >
                              <Trash2 size={14} />
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* 페이지네이션 */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-6 py-4 border-t border-slate-800">
            <p className="text-sm text-slate-500">
              {products.length}개 중 {(page - 1) * perPage + 1}–{Math.min(page * perPage, products.length)}
            </p>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="p-2 rounded-lg bg-slate-800 text-slate-400 hover:text-white disabled:opacity-30 transition"
              >
                <ChevronLeft size={16} />
              </button>
              <span className="text-sm text-slate-400 px-3">
                {page} / {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="p-2 rounded-lg bg-slate-800 text-slate-400 hover:text-white disabled:opacity-30 transition"
              >
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ═══ 상품 등록/수정 모달 ═══ */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
          <div 
            className="bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl w-full overflow-y-auto"
            style={{ maxWidth: "96vw", width: "96vw", maxHeight: "95vh" }}
          >
            {/* 모달 헤더 */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-blue-500/15 text-blue-400 flex items-center justify-center">
                  {isEditMode ? <Edit3 size={20} /> : <Plus size={20} />}
                </div>
                <div>
                  <h3 className="text-lg font-bold text-white">{isEditMode ? "상품 상세 수정" : "새 상품 등록"}</h3>
                  <p className="text-xs text-slate-500">
                    {isEditMode ? "상품의 모든 세부 정보를 수정하고 업데이트합니다." : "수동으로 상품을 등록합니다 (크롤러 미경유)"}
                  </p>
                </div>
              </div>
              <button onClick={() => { setShowCreateModal(false); setIsEditMode(false); setEditingId(null); }} className="p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition">
                <X size={20} />
              </button>
            </div>

            {/* 모달 본문 */}
            <div className="p-6">
              {/* 윈윈크롤러3 스마트 수집 패널 (3단계) */}
              <div className="mb-6 bg-slate-950/60 border border-purple-900/40 rounded-2xl p-5 space-y-4 shadow-lg shadow-purple-950/10">
                <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                  <h4 className="text-xs font-bold text-purple-400 flex items-center gap-1.5">
                    <Cpu size={14} /> 🚀 윈윈크롤러3 스마트 1초 수집 및 자동 번역 연동
                  </h4>
                  <span className="text-[10px] text-slate-500">* 카테고리를 먼저 하단에서 선택한 후 수집을 진행해 주세요.</span>
                </div>
                
                <div className="flex flex-col md:flex-row items-stretch md:items-center gap-3">
                  {/* 플랫폼 선택 탭 */}
                  <div className="flex bg-slate-900 p-0.5 rounded-lg border border-slate-800 shrink-0">
                    {[
                      { key: "weishang", label: "웨이상 앨범" },
                      { key: "band", label: "네이버 밴드 (예정)" },
                      { key: "kakao", label: "카카오스토리 (예정)" }
                    ].map(tab => (
                      <button
                        key={tab.key}
                        type="button"
                        onClick={() => tab.key === "weishang" && setScrapePlatform(tab.key)}
                        disabled={tab.key !== "weishang"}
                        className={`px-3 py-1.5 text-xs font-bold rounded-md transition ${
                          scrapePlatform === tab.key 
                            ? "bg-purple-600 text-white shadow" 
                            : tab.key !== "weishang" 
                              ? "text-slate-600 cursor-not-allowed" 
                              : "text-slate-400 hover:text-white"
                        }`}
                      >
                        {tab.label}
                      </button>
                    ))}
                  </div>

                  {/* URL 입력창 */}
                  <div className="flex-1">
                    <input
                      type="text"
                      placeholder={
                        scrapePlatform === "weishang"
                          ? "수집할 웨이상 업체 앨범 URL 주소를 입력하세요 (예: https://www.szwego.com/...)"
                          : "플랫폼 수집 주소 URL을 입력하세요"
                      }
                      value={scrapeUrl}
                      onChange={e => setScrapeUrl(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-700 focus:outline-none focus:border-purple-600 transition"
                    />
                  </div>

                  {/* 수집 개수 및 실행 버튼 */}
                  <div className="flex items-center gap-2 shrink-0">
                    <div className="flex items-center gap-1.5 bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5">
                      <span className="text-[10px] text-slate-500 font-medium">개수:</span>
                      <input
                        type="number"
                        min="1"
                        max="20"
                        value={scrapeCount}
                        onChange={e => setScrapeCount(Math.max(1, parseInt(e.target.value) || 1))}
                        className="w-8 bg-transparent text-xs text-center text-white font-bold focus:outline-none"
                      />
                    </div>
                    
                    <button
                      type="button"
                      onClick={handlePlatformScrape}
                      disabled={scrapeLoading || !scrapeUrl}
                      className="bg-gradient-to-r from-purple-600 to-indigo-650 hover:from-purple-500 hover:to-indigo-550 text-white font-bold px-4 py-2 rounded-lg text-xs transition flex items-center gap-1.5 shadow-md shadow-purple-950/20 disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      {scrapeLoading ? (
                        <>
                          <Loader2 size={12} className="animate-spin" />
                          스마트 수집 및 AI 번역 중...
                        </>
                      ) : (
                        <>
                          <Cpu size={12} />
                          스마트 수집 실행
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </div>

              {/* 1. 상단 2단 그리드 영역 (기본 입력 정보 / 이미지 업로더) */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 mb-6">
                
                {/* 좌측 컬럼 (7열) - 상품 정보 폼 */}
                <div className="lg:col-span-7 space-y-5">
                  {/* 상품명 (한국어) */}
                  <div>
                    <label className="block text-sm font-semibold text-slate-300 mb-1.5">상품명 (한국어) <span className="text-red-400">*</span></label>
                    <input
                      type="text" placeholder="예: 프리미엄 캐시미어 코트"
                      value={createForm.kr_name} onChange={e => setCreateForm(f => ({ ...f, kr_name: e.target.value }))}
                      className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-white text-sm placeholder:text-slate-500 focus:outline-none focus:border-blue-500 transition"
                    />
                  </div>

                  {/* 동영상 입력 폼 */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <label className="block text-sm font-semibold text-slate-300 flex items-center gap-1.5">
                        <Play size={14} className="text-blue-500" /> 상품 대표 동영상 (직접 등록 / URL 링크)
                      </label>
                      <div className="flex bg-slate-950 p-0.5 rounded-lg border border-slate-800">
                        <button
                          type="button"
                          onClick={() => setVideoMode("url")}
                          className={`px-2.5 py-1 text-[11px] font-bold rounded-md transition ${
                            videoMode === "url" ? "bg-blue-600 text-white" : "text-slate-400 hover:text-white"
                          }`}
                        >
                          외부 URL 링크
                        </button>
                        <button
                          type="button"
                          onClick={() => setVideoMode("upload")}
                          className={`px-2.5 py-1 text-[11px] font-bold rounded-md transition ${
                            videoMode === "upload" ? "bg-blue-600 text-white" : "text-slate-400 hover:text-white"
                          }`}
                        >
                          직접 파일 업로드
                        </button>
                      </div>
                    </div>

                    {videoMode === "url" ? (
                      <input
                        type="text"
                        placeholder="예: https://example.com/videos/product1.mp4 또는 YouTube 링크"
                        value={createForm.video_url}
                        onChange={e => setCreateForm(f => ({ ...f, video_url: e.target.value }))}
                        className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-white text-sm placeholder:text-slate-500 focus:outline-none focus:border-blue-500 transition font-mono"
                      />
                    ) : (
                      <div className="flex gap-2">
                        <input
                          ref={videoFileInputRef}
                          type="file"
                          accept="video/*"
                          onChange={handleVideoUpload}
                          className="hidden"
                        />
                        <button
                          type="button"
                          onClick={() => videoFileInputRef.current?.click()}
                          disabled={videoUploading}
                          className="flex-1 bg-slate-800 hover:bg-slate-750 border border-slate-700 text-slate-300 hover:text-white py-2.5 px-4 rounded-xl text-sm font-semibold flex items-center justify-center gap-2 transition"
                        >
                          {videoUploading ? (
                            <>
                              <Loader2 size={16} className="animate-spin text-blue-450" />
                              동영상 업로드 중...
                            </>
                          ) : (
                            <>
                              <Upload size={16} />
                              동영상 파일 선택 (MP4, AVI 등)
                            </>
                          )}
                        </button>
                        {createForm.video_url && (
                          <div className="flex items-center gap-1.5 bg-slate-950 border border-slate-800 rounded-xl px-3 max-w-[240px] truncate">
                            <span className="text-[11px] text-blue-400 truncate flex-1 font-mono">{createForm.video_url.substring(createForm.video_url.lastIndexOf("/") + 1)}</span>
                            <button
                              type="button"
                              onClick={() => setCreateForm(f => ({ ...f, video_url: "" }))}
                              className="text-red-400 hover:text-red-300"
                              title="삭제"
                            >
                              <X size={14} />
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* 가격 세부 폼 */}
                  <div className="grid grid-cols-3 gap-4">
                    <div>
                      <label className="block text-sm font-semibold text-slate-300 mb-1.5">판매가 (원) <span className="text-red-400">*</span></label>
                      <input
                        type="number" placeholder="100000"
                        value={createForm.base_price} onChange={e => handleBasePriceChange(e.target.value)}
                        className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-white text-sm placeholder:text-slate-500 focus:outline-none focus:border-blue-500 transition"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-semibold text-slate-300 mb-1.5">할인가 (원)</label>
                      <input
                        type="number" placeholder="70000"
                        value={createForm.sale_price} onChange={e => handleSalePriceChange(e.target.value)}
                        className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-white text-sm placeholder:text-slate-500 focus:outline-none focus:border-blue-500 transition"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-semibold text-slate-300 mb-1.5">할인율 (%)</label>
                      <input
                        type="number" placeholder="30"
                        value={createForm.discount_rate} onChange={e => handleDiscountRateChange(e.target.value)}
                        className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-white text-sm placeholder:text-slate-500 focus:outline-none focus:border-blue-500 transition"
                      />
                    </div>
                  </div>

                  {/* 재고 / SKU */}
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-semibold text-slate-300 mb-1.5">전체 재고 수량 <span className="text-[10px] text-blue-400 font-normal">(상세 옵션 합산)</span></label>
                      <input
                        type="number"
                        readOnly={Object.keys(optionStocks).length > 0}
                        placeholder="0"
                        value={createForm.stock_quantity}
                        onChange={e => {
                          if (Object.keys(optionStocks).length === 0) {
                            setCreateForm(f => ({ ...f, stock_quantity: e.target.value }));
                          }
                        }}
                        className={`w-full border border-slate-700 rounded-xl px-4 py-2.5 text-sm focus:outline-none font-bold transition-all ${
                          Object.keys(optionStocks).length > 0
                            ? "bg-slate-800/60 text-slate-400 cursor-not-allowed border-slate-800"
                            : "bg-slate-800 text-white border-slate-700 focus:border-blue-500"
                        }`}
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-semibold text-slate-300 mb-1.5">SKU 코드</label>
                      <input
                        type="text" placeholder="LUX-001"
                        value={createForm.sku} onChange={e => setCreateForm(f => ({ ...f, sku: e.target.value }))}
                        className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-white text-sm placeholder:text-slate-500 focus:outline-none focus:border-blue-500 transition"
                      />
                    </div>
                  </div>

                  {/* 카테고리 선택 */}
                  <div>
                    <label className="block text-sm font-semibold text-slate-300 mb-1.5">카테고리 <span className="text-red-400">*</span></label>
                    <select
                      value={createForm.category_id} onChange={e => handleCategoryChange(e.target.value)}
                      className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 transition"
                    >
                      <option value="">카테고리 선택...</option>
                      {(() => {
                        const options: React.ReactNode[] = [];
                        const parents = categories.filter(c => !c.parent_id);
                        parents.forEach(parent => {
                          options.push(
                            <option key={parent.id} value={parent.id} className="font-bold text-slate-100 bg-slate-900">
                              {parent.name} (대분류)
                            </option>
                          );
                          const midCats = categories.filter(c => c.parent_id === parent.id);
                          midCats.forEach(mid => {
                            options.push(
                              <option key={mid.id} value={mid.id} className="text-slate-300 bg-slate-900 font-semibold">
                                {"\u00A0\u00A0ㄴ "}{mid.name} (중분류)
                              </option>
                            );
                            const subCats = categories.filter(c => c.parent_id === mid.id);
                            subCats.forEach(sub => {
                              options.push(
                                <option key={sub.id} value={sub.id} className="text-slate-400 bg-slate-900">
                                  {"\u00A0\u00A0\u00A0\u00A0ㄴ "}{sub.name}
                                </option>
                              );
                            });
                          });
                        });
                        return options;
                      })()}
                    </select>
                  </div>

                  {/* 카테고리별 상세 재고 규격화 매트릭스 UI */}
                  <div className="space-y-3 bg-slate-950/40 p-4 rounded-xl border border-slate-800">
                    <div className="flex items-center justify-between border-b border-slate-850 pb-2">
                      <label className="block text-xs font-bold text-slate-300 flex items-center gap-1.5">
                        📦 카테고리별 상세 재고 매트릭스 (실시간 수량 합산)
                      </label>
                      <span className="text-[10px] text-slate-500">카테고리 선택에 따라 규격이 자동 매핑됩니다.</span>
                    </div>

                    {Object.keys(optionStocks).length > 0 ? (
                      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                        {Object.entries(optionStocks).map(([key, qty]) => (
                          <div key={key} className="flex items-center justify-between bg-slate-900 border border-slate-850 rounded-lg p-1.5">
                            <span className="text-xs font-bold text-slate-400 truncate max-w-[70px] pl-1" title={key}>{key}</span>
                            <div className="flex items-center gap-1">
                              <input
                                type="number"
                                min="0"
                                placeholder="0"
                                value={qty === 0 ? "" : qty}
                                onChange={e => handleOptionStockChange(key, e.target.value)}
                                className="w-16 bg-slate-800 border border-slate-700 rounded px-1.5 py-0.5 text-xs text-white focus:outline-none focus:border-blue-500 text-center font-semibold"
                              />
                              <button
                                type="button"
                                onClick={() => removeOptionKey(key)}
                                className="text-slate-500 hover:text-red-400 p-0.5 transition"
                                title="옵션 규격 삭제"
                              >
                                <X size={12} />
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-slate-500 text-center py-2">카테고리를 선택하거나 커스텀 옵션 규격을 추가해 주세요.</p>
                    )}

                    {/* 커스텀 규격 추가 */}
                    <div className="flex gap-2 pt-2 border-t border-slate-900">
                      <input
                        type="text"
                        placeholder="예: XXL, 블랙-L 등 커스텀 규격 입력"
                        value={customOptionVal}
                        onChange={e => setCustomOptionVal(e.target.value)}
                        onKeyDown={e => e.key === "Enter" && addCustomOptionKey()}
                        className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-blue-500"
                      />
                      <button
                        type="button"
                        onClick={addCustomOptionKey}
                        className="px-3 py-1 bg-slate-800 hover:bg-slate-750 text-slate-300 rounded-lg text-xs font-bold transition flex items-center gap-1 shrink-0"
                      >
                        <Plus size={12} /> 옵션 추가
                      </button>
                    </div>
                  </div>

                  {/* 태그 키워드 */}
                  <div>
                    <label className="block text-sm font-semibold text-slate-300 mb-1.5">태그 키워드 (쉼표 구분)</label>
                    <input
                      type="text" placeholder="예: 겨울, 울 코트, 오버핏"
                      value={createForm.tag_string} onChange={e => setCreateForm(f => ({ ...f, tag_string: e.target.value }))}
                      className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-white text-sm placeholder:text-slate-500 focus:outline-none focus:border-blue-500 transition"
                    />
                  </div>
                </div>

                {/* 우측 컬럼 (5열) - 이미지 업로드 & VTON 제어 */}
                <div className="lg:col-span-5 space-y-6">
                  {/* 스마트 이미지 업로더 */}
                  <SmartImageUploader
                    images={createForm.images}
                    onImagesChange={(imgs) => setCreateForm(f => ({ ...f, images: imgs }))}
                    mainImageUrl={createForm.ai_fitting_image_url}
                    onMainImageUrlChange={(url) => setCreateForm(f => ({ ...f, ai_fitting_image_url: url }))}
                  />

                  {/* VTON 피팅용 누끼 이미지 (PNG 권장) */}
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <label className="block text-sm font-semibold text-slate-300">
                        <Cpu size={14} className="inline mr-1.5 -mt-0.5 text-purple-400" />
                        가상 피팅(VTON) 누끼 이미지 <span className="text-slate-500 font-normal">(PNG 권장)</span>
                        <span className="text-[10px] text-purple-400 block mt-0.5 font-normal">* 배경이 투명하게 제거된 이미지를 업로드해야 가상 피팅이 정상 작동합니다.</span>
                      </label>
                    </div>

                    {/* VTON 업로드 영역 */}
                    <div
                      onClick={() => !vtonUploading && vtonFileInputRef.current?.click()}
                      className={`relative border-2 border-dashed border-slate-700 hover:border-slate-500 bg-slate-800/50 hover:bg-slate-800 rounded-xl p-6 transition-all cursor-pointer flex flex-col items-center justify-center min-h-[140px]`}
                    >
                      <input
                        ref={vtonFileInputRef}
                        type="file"
                        accept="image/png, image/jpeg, image/webp"
                        onChange={handleVtonUpload}
                        className="hidden"
                      />

                      {vtonUploading ? (
                        <div className="flex flex-col items-center gap-2">
                          <Loader2 size={24} className="animate-spin text-purple-400" />
                          <span className="text-xs text-slate-400">누끼 이미지 업로드 중...</span>
                        </div>
                      ) : createForm.transparent_item_image_url ? (
                        <div className="relative w-full flex flex-col items-center justify-center gap-2 group">
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img
                            src={createForm.transparent_item_image_url}
                            alt="Transparent Item Preview"
                            className="max-h-24 object-contain rounded-lg bg-slate-950 p-1 border border-slate-800"
                          />
                          <span className="text-[11px] text-slate-400 truncate max-w-full block font-mono px-2">
                            {createForm.transparent_item_image_url}
                          </span>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setCreateForm(f => ({ ...f, transparent_item_image_url: "" }));
                            }}
                            className="absolute -top-1 -right-1 bg-red-600 hover:bg-red-500 text-white rounded-full p-1 transition shadow-lg"
                          >
                            <X size={12} />
                          </button>
                        </div>
                      ) : (
                        <div className="text-center space-y-2">
                          <Upload size={20} className="mx-auto text-slate-500 group-hover:text-slate-300 transition" />
                          <div className="text-xs font-medium text-slate-300">투명 배경 PNG 이미지 업로드</div>
                          <p className="text-[10px] text-slate-500">클릭하여 이미지 찾기</p>
                        </div>
                      )}
                    </div>

                    {/* 직접 URL 입력 */}
                    <div>
                      <input
                        type="text"
                        placeholder="누끼 이미지 URL 직접 입력 (선택사항)"
                        value={createForm.transparent_item_image_url}
                        onChange={e => setCreateForm(f => ({ ...f, transparent_item_image_url: e.target.value }))}
                        className="w-full bg-slate-800/80 border border-slate-700 rounded-lg px-3 py-1.5 text-white text-xs placeholder:text-slate-500 focus:outline-none focus:border-purple-500 transition font-mono"
                      />
                    </div>

                    {/* 수동 AI 누끼 생성 기능 (후작업) */}
                    {isEditMode && editingId && (
                      <div className="mt-4 p-4 border border-slate-700/80 rounded-xl bg-slate-900/60 space-y-3">
                        <div className="flex items-center gap-2">
                          <Cpu size={14} className="text-purple-400" />
                          <span className="text-xs font-bold text-slate-350">
                            수동 AI 누끼(배경 제거) 가공
                          </span>
                        </div>
                        <p className="text-[10px] text-slate-500 leading-relaxed">
                          상품 갤러리 또는 대표 이미지 중 1컷을 선택하여 배경을 제거하고 투명 누끼 이미지를 생성합니다. (AI API 비용이 청구됩니다)
                        </p>

                        {/* 이미지 선택 셀렉터 */}
                        <div className="space-y-2">
                          <label className="block text-[11px] font-semibold text-slate-405">가공할 이미지 선택</label>
                          <div className="flex gap-2 overflow-x-auto pb-2 max-w-full scrollbar-thin scrollbar-thumb-slate-800">
                            {/* 대표 이미지 */}
                            {createForm.ai_fitting_image_url && (
                              <button
                                type="button"
                                onClick={() => setSelectedExtractImage(createForm.ai_fitting_image_url)}
                                className={`relative shrink-0 w-12 h-12 rounded-lg border-2 overflow-hidden bg-slate-950 p-0.5 transition-all ${
                                  selectedExtractImage === createForm.ai_fitting_image_url
                                    ? "border-purple-500 scale-95"
                                    : "border-slate-800 hover:border-slate-650"
                                }`}
                              >
                                {/* eslint-disable-next-line @next/next/no-img-element */}
                                <img
                                  src={createForm.ai_fitting_image_url}
                                  alt="Main"
                                  className="w-full h-full object-contain"
                                />
                                <div className="absolute bottom-0 left-0 right-0 bg-purple-600/90 text-[8px] text-white text-center py-0.5 font-bold">
                                  대표
                                </div>
                              </button>
                            )}
                            
                            {/* 나머지 갤러리 이미지들 */}
                            {createForm.images.map((imgUrl, idx) => (
                              <button
                                key={idx}
                                type="button"
                                onClick={() => setSelectedExtractImage(imgUrl)}
                                className={`relative shrink-0 w-12 h-12 rounded-lg border-2 overflow-hidden bg-slate-950 p-0.5 transition-all ${
                                  selectedExtractImage === imgUrl
                                    ? "border-purple-500 scale-95"
                                    : "border-slate-800 hover:border-slate-650"
                                }`}
                              >
                                {/* eslint-disable-next-line @next/next/no-img-element */}
                                <img
                                  src={imgUrl}
                                  alt={`Gallery ${idx + 1}`}
                                  className="w-full h-full object-contain"
                                />
                                <div className="absolute bottom-0 left-0 right-0 bg-slate-800/90 text-[8px] text-slate-300 text-center py-0.5 font-mono">
                                  #{idx + 1}
                                </div>
                              </button>
                            ))}
                          </div>
                        </div>

                        {/* 실행 버튼 */}
                        <button
                          type="button"
                          onClick={handleExtractTransparent}
                          disabled={isExtractingTransparent || !selectedExtractImage}
                          className="w-full py-2 bg-gradient-to-r from-purple-700 to-indigo-700 hover:from-purple-600 hover:to-indigo-600 text-white font-bold rounded-lg text-xs transition flex items-center justify-center gap-1.5 shadow-md disabled:opacity-40 disabled:cursor-not-allowed"
                        >
                          {isExtractingTransparent ? (
                            <>
                              <Loader2 size={12} className="animate-spin text-white" />
                              AI 누끼 가공 진행 중 (약 3~5초 소요)...
                            </>
                          ) : (
                            <>
                              <Cpu size={12} />
                              선택한 이미지 AI 누끼 생성하기 (1컷)
                            </>
                          )}
                        </button>
                      </div>
                    )}
                  </div>
                </div>

              </div>

              {/* 2. 하단 1단 100% 영역 (상세 설명 에디터 단독 와이드 배치) */}
              <div className="border-t border-slate-800 pt-6 mt-6 space-y-5">
                {/* 상품 상세 설명 (TipTap 리치 에디터) */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between mb-1">
                    <label className="block text-sm font-semibold text-slate-300">상품 상세 설명 (이미지 및 하이퍼링크 업로드 가능)</label>
                    <button
                      type="button"
                      onClick={handleAIAutofill}
                      disabled={autofilling || !createForm.kr_name}
                      className="text-xs bg-gradient-to-r from-blue-600 to-purple-650 hover:from-blue-500 hover:to-purple-550 text-white font-bold px-2.5 py-1 rounded-lg transition-all flex items-center gap-1 shadow-md disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      {autofilling ? (
                        <>
                          <Loader2 size={10} className="animate-spin text-white" />
                          AI 설명 작성 중...
                        </>
                      ) : (
                        <>
                          <Cpu size={10} />
                          ✨ AI 1초 자동 완성 (기본 텍스트)
                        </>
                      )}
                    </button>
                  </div>
                  
                  {/* TipTap 리치 텍스트 에디터 탑재 (가로 100% 꽉 찬 와이드형) */}
                  <div className="border border-slate-700 rounded-xl overflow-hidden bg-slate-850">
                    <RichEditor
                      value={createForm.description_html}
                      onChange={html => setCreateForm(f => ({ ...f, description_html: html }))}
                    />
                  </div>
                </div>

                {/* AI 작문 텍스트에리어 백업 (참조/수정용) */}
                <div>
                  <label className="block text-xs font-semibold text-slate-500 mb-1">AI 텍스트 백업 (참고용 텍스트)</label>
                  <textarea
                    rows={2} placeholder="AI 1초 자동 완성을 누르면 이 영역에 참고용 기본 텍스트 설명이 생성됩니다."
                    value={createForm.kr_description || ""} onChange={e => setCreateForm(f => ({ ...f, kr_description: e.target.value }))}
                    className="w-full bg-slate-800/40 border border-slate-800 rounded-lg px-3 py-1.5 text-slate-400 text-xs placeholder:text-slate-600 focus:outline-none resize-none leading-normal"
                  />
                </div>
              </div>
            </div>

            {/* 모달 푸터 */}
            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-slate-800">
              <button
                onClick={() => { setShowCreateModal(false); setIsEditMode(false); setEditingId(null); }}
                className="px-5 py-2.5 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-750 hover:text-white transition font-medium text-sm"
              >
                취소
              </button>
              <button
                disabled={creating || !createForm.kr_name || !createForm.base_price || !createForm.category_id}
                onClick={handleCreateProduct}
                className="px-6 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium text-sm transition disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {creating ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
                {creating ? (isEditMode ? "저장 중..." : "등록 중...") : (isEditMode ? "상품 수정 완료" : "상품 등록")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
