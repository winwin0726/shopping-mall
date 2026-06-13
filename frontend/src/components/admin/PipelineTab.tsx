"use client";
import { authFetch, API_URL } from "@/lib/api";

import React, { useEffect, useState, useRef } from "react";
import { Box, CheckCircle, XCircle, Loader2, AlertCircle, RefreshCw, Play, Send, X, Search, Filter, ExternalLink, Edit, LayoutGrid, Grid, List, Trash2, ArrowLeft, ArrowRight, CheckSquare, Square, ChevronUp, ChevronDown, Plus, Star, Eye, GripVertical, ArrowRightLeft, Upload } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import Image from "next/image";

interface PendingProduct {
  id: number;
  originalName: string;
  name: string;
  price: number;
  margin: string;
  imageUrl: string | null;
  description: string;
  images: string[];
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

// 한글 초성 및 영문 첫 글자 추출을 위한 헬퍼 함수
function getInitialChar(str: string): string {
  if (!str) return "";
  
  // 1. 문자열 내에서 최초로 등장하는 한글 음절, 한글 자모, 또는 영문자를 추출하여 특수문자나 보이지 않는 공백을 건너뜀
  const match = str.match(/[ㄱ-ㅎ가-힣A-Za-z]/);
  if (!match) {
    return str.trim().charAt(0).toUpperCase();
  }
  
  const char = match[0];
  const charCode = char.charCodeAt(0);
  
  // 2. 한글 유니코드 범위 (가 ~ 힣)
  if (charCode >= 44032 && charCode <= 55203) {
    const hangulIndex = Math.floor((charCode - 44032) / 588);
    const initials = [
      "ㄱ", "ㄲ", "ㄴ", "ㄷ", "ㄸ", "ㄹ", "ㅁ", "ㅂ", "ㅃ",
      "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅉ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"
    ];
    const initial = initials[hangulIndex];
    
    // 쌍자음 맵핑 (ㄲ -> ㄱ, ㄸ -> ㄷ 등)
    const doubleJaumMap: { [key: string]: string } = {
      "ㄲ": "ㄱ",
      "ㄸ": "ㄷ",
      "ㅃ": "ㅂ",
      "ㅆ": "ㅅ",
      "ㅉ": "ㅈ"
    };
    return doubleJaumMap[initial] || initial;
  }
  
  // 3. 한글 자모가 직접 입력된 경우 (예: ㄱ, ㄴ 등)
  if (charCode >= 12593 && charCode <= 12622) {
    const initial = char;
    const doubleJaumMap: { [key: string]: string } = {
      "ㄲ": "ㄱ",
      "ㄸ": "ㄷ",
      "ㅃ": "ㅂ",
      "ㅆ": "ㅅ",
      "ㅉ": "ㅈ"
    };
    return doubleJaumMap[initial] || initial;
  }
  
  // 4. 영문 대소문자
  return char.toUpperCase();
}

export default function PipelineTab() {
  const apiUrl = API_URL;
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
  const [activeTab, setActiveTab] = useState<"vendors" | "direct" | "saved">("vendors"); // 탭 선택 상태 추가 (saved 탭 포함)
  const [selectedInitial, setSelectedInitial] = useState<string>("전체");
  const hangulInitials = ["ㄱ", "ㄴ", "ㄷ", "ㄹ", "ㅁ", "ㅂ", "ㅅ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"];

  // 수집 설정 모달 상태
  const [showScrapeModal, setShowScrapeModal] = useState(false);
  const [selectedVendor, setSelectedVendor] = useState<Vendor | null>(null);
  const [scrapeCount, setScrapeCount] = useState(5);
  const [scrapeCategoryId, setScrapeCategoryId] = useState("");
  const [bulkScrapeCategoryId, setBulkScrapeCategoryId] = useState(""); // 일괄 수집용 카테고리 상태 추가
  const [directScrapeCategoryId, setDirectScrapeCategoryId] = useState(""); // 직접 URL 수집용 카테고리 상태 추가
  const [exchangeRate, setExchangeRate] = useState(200.0);
  const [marginRate, setMarginRate] = useState(1.3);
  const [isCrawling, setIsCrawling] = useState(false);
  const [crawlStatus, setCrawlStatus] = useState<{type: "success"|"error", msg: string} | null>(null);

  // 승인 모달 상태
  const [showApproveModal, setShowApproveModal] = useState(false);
  const [selectedProductId, setSelectedProductId] = useState<number | null>(null);
  const [selectedCategoryId, setSelectedCategoryId] = useState<string>("");

  // 레이아웃 모드 ('grid3' | 'grid4' | 'grid5' | 'list')
  const [layoutMode, setLayoutMode] = useState<'grid3' | 'grid4' | 'grid5' | 'list'>('grid3');

  // 편집 모달 (퀵 에디터) 상태
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingProduct, setEditingProduct] = useState<PendingProduct | null>(null);
  const [editName, setEditName] = useState("");
  const [editPrice, setEditPrice] = useState<number>(0);
  const [editDesc, setEditDesc] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  // 다중 선택 상태 (체크박스)
  const [selectedProductIds, setSelectedProductIds] = useState<number[]>([]);
  
  // 마우스 드래그/Shift 선택 범위 내에 들어와 있는 포커스 대상 상품 ID 목록
  const [focusedProductIds, setFocusedProductIds] = useState<number[]>([]);

  // 키보드 포커스 네비게이션 인덱스
  const [focusedIndex, setFocusedIndex] = useState<number>(-1);
  const containerRef = React.useRef<HTMLDivElement>(null);

  // 일괄 가격 수정 모달 상태
  const [showBulkPriceModal, setShowBulkPriceModal] = useState(false);
  const [bulkPriceChange, setBulkPriceChange] = useState<number>(10000);
  const [bulkPriceAction, setBulkPriceAction] = useState<'add' | 'sub' | 'set'>('add'); // 인상, 인하, 변경

  // 실시간 크롤 로그 및 수집 진행 시뮬레이션 상태
  const [liveLogs, setLiveLogs] = useState<string[]>([]);
  const [isScrapingProgress, setIsScrapingProgress] = useState(false);
  const [scrapeProgressValue, setScrapeProgressValue] = useState(0);

  // 에디터용 이미지 배열 상태
  const [editImages, setEditImages] = useState<string[]>([]);

  // 에디터용 이미지 관리 추가 상태 변수들 (윈윈크롤러 3.3 스펙)
  const [editSelectedIndices, setEditSelectedIndices] = useState<number[]>([]);
  const [urlInputActive, setUrlInputActive] = useState(false);
  const [newImageUrl, setNewImageUrl] = useState("");
  const [transferringIndex, setTransferringIndex] = useState<number | null>(null);
  const [transferSearchQuery, setTransferSearchQuery] = useState("");
  const [transferSearchResults, setTransferSearchResults] = useState<PendingProduct[]>([]);
  const [editContextMenu, setEditContextMenu] = useState<{ show: boolean; x: number; y: number; index: number; url: string } | null>(null);
  const [imageUploadLoading, setImageUploadLoading] = useState(false);
  const [editDraggedIndex, setEditDraggedIndex] = useState<number | null>(null);
  const [enlargedUrl, setEnlargedUrl] = useState<string | null>(null);
  const quickEditFileInputRef = useRef<HTMLInputElement>(null);

  // 벤더 다중 선택 및 10개 에이전트 채널 시뮬레이션 상태
  const [selectedVendorIds, setSelectedVendorIds] = useState<string[]>([]);
  
  // 10개 에이전트 인터페이스 정의
  interface AgentStatus {
    id: number;
    name: string;
    vendorName: string;
    status: "idle" | "preparing" | "crawling" | "verifying" | "translating" | "completed" | "failed";
    progress: number;
    currentAction: string;
  }
  const [agentStatuses, setAgentStatuses] = useState<AgentStatus[]>(
    Array.from({ length: 10 }, (_, i) => ({
      id: i + 1,
      name: `수집봇 #${i + 1}`,
      vendorName: "-",
      status: "idle",
      progress: 0,
      currentAction: "대기 중"
    }))
  );

  // 일괄 승인 카테고리 지정 모달 상태
  const [showBulkApproveModal, setShowBulkApproveModal] = useState(false);
  const [bulkApproveCategoryId, setBulkApproveCategoryId] = useState("");

  // 실시간 가상 리소스 계기판 상태
  const [systemStats, setSystemStats] = useState({ cpu: 12, mem: 1.8, speed: 0 });

  // Shift 일괄 선택의 기준점이 될 마지막 선택 인덱스
  const [lastSelectedIndex, setLastSelectedIndex] = useState<number>(-1);

  // 수집 결과 팝업 및 저장 이력 상태 변수들
  const [showScrapeResultModal, setShowScrapeResultModal] = useState(false);
  const [scrapedResults, setScrapedResults] = useState<any[]>([]);
  const [scrapedSessionInfo, setScrapedSessionInfo] = useState<{
    date: string;
    targetName: string;
    totalCount: number;
    estimatedMargin: number;
    categoryName: string;
  } | null>(null);
  const [savedSessions, setSavedSessions] = useState<any[]>([]);
  const [selectedSavedSession, setSelectedSavedSession] = useState<any | null>(null);

  // 컴포넌트 마운트 시 로컬스토리지에서 저장된 수집 세션 이력 로드
  useEffect(() => {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem("saved_scrape_sessions");
      if (stored) {
        try {
          setSavedSessions(JSON.parse(stored));
        } catch (e) {
          console.error("Failed to load saved scrape sessions", e);
        }
      }
    }
  }, []);

  const openEditModal = (p: PendingProduct) => {
    setEditingProduct(p);
    setEditName(p.name);
    setEditPrice(p.price);
    setEditDesc(p.description || "");
    setEditImages(p.images || []);
    setEditSelectedIndices([]);
    setTransferringIndex(null);
    setTransferSearchQuery("");
    setTransferSearchResults([]);
    setEditContextMenu(null);
    setShowEditModal(true);
  };

  // 우클릭 컨텍스트 메뉴 바깥 클릭 시 닫기
  useEffect(() => {
    const handleGlobalClick = () => {
      if (editContextMenu) setEditContextMenu(null);
    };
    window.addEventListener("click", handleGlobalClick);
    return () => window.removeEventListener("click", handleGlobalClick);
  }, [editContextMenu]);

  // 퀵 에디터 이미지 업로드 핸들러
  const uploadEditFiles = async (files: FileList | File[]) => {
    const imageFiles = Array.from(files).filter(f => f.type.startsWith("image/"));
    if (imageFiles.length === 0) return;
    if (editImages.length + imageFiles.length > 30) {
      alert("최대 30장까지 업로드 가능합니다.");
      return;
    }
    setImageUploadLoading(true);
    try {
      const formData = new FormData();
      imageFiles.forEach(f => formData.append("files", f));
      const res = await authFetch(`${apiUrl}/api/admin/upload/multiple`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) throw new Error("업로드 실패");
      const data = await res.json();
      const newUrls = data.uploaded.map((u: any) => u.url);
      setEditImages(prev => [...prev, ...newUrls]);
      if (data.errors?.length > 0) {
        alert(`${data.errors.length}개 파일 업로드 실패: ${data.errors.map((e: any) => e.filename).join(", ")}`);
      }
    } catch (err: any) {
      alert(err.message);
    } finally {
      setImageUploadLoading(false);
    }
  };

  // 퀵 에디터 이미지 URL 추가 핸들러
  const handleEditAddImageUrl = () => {
    const url = newImageUrl.trim();
    if (!url) return;
    if (!url.startsWith("http")) {
      alert("올바른 URL을 입력하세요 (http:// 또는 https://)");
      return;
    }
    if (editImages.length >= 30) {
      alert("최대 30장까지 등록 가능합니다.");
      return;
    }
    setEditImages(prev => [...prev, url]);
    setNewImageUrl("");
    setUrlInputActive(false);
  };

  // 퀵 에디터 이미지 드래그앤드롭 순서 정렬 핸들러
  const handleEditImgDragStart = (index: number) => {
    setEditDraggedIndex(index);
  };

  const handleEditImgDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault();
  };

  const handleEditImgDrop = (index: number) => {
    if (editDraggedIndex === null || editDraggedIndex === index) return;
    const updated = [...editImages];
    const draggedItem = updated[editDraggedIndex];
    updated.splice(editDraggedIndex, 1);
    updated.splice(index, 0, draggedItem);
    setEditImages(updated);
    setEditDraggedIndex(null);
  };

  // 퀵 에디터 우클릭 컨텍스트 메뉴 오픈 핸들러
  const handleEditContextMenu = (e: React.MouseEvent, index: number, url: string) => {
    e.preventDefault();
    setEditContextMenu({
      show: true,
      x: e.clientX,
      y: e.clientY,
      index,
      url,
    });
  };

  // 퀵 에디터 대표 이미지로 지정 핸들러
  const handleEditSetAsPrimary = (index: number) => {
    if (index === 0) return;
    const updated = [...editImages];
    const target = updated[index];
    updated.splice(index, 1);
    updated.unshift(target);
    setEditImages(updated);
    setEditSelectedIndices([]);
  };

  // 다른 대기소 상품으로 이미지 이동을 위한 검색 핸들러
  const handleEditTransferSearch = (query: string) => {
    setTransferSearchQuery(query);
    if (!query.trim()) {
      setTransferSearchResults([]);
      return;
    }
    const clean = query.trim().toLowerCase();
    const results = products.filter(
      p =>
        p.id !== editingProduct?.id &&
        (String(p.id).includes(clean) || p.name.toLowerCase().includes(clean))
    );
    setTransferSearchResults(results);
  };

  // 이미지를 다른 상품으로 실제 양도 및 백엔드 저장 핸들러
  const handleMoveImageToProduct = async (targetProduct: PendingProduct, index: number) => {
    const imageUrl = editImages[index];
    if (!imageUrl) return;
    
    const targetImages = targetProduct.images ? [...targetProduct.images] : [];
    if (targetImages.includes(imageUrl)) {
      alert("대상 상품에 이미 동일한 이미지가 존재합니다.");
      return;
    }
    targetImages.push(imageUrl);

    try {
      const res = await authFetch(`${apiUrl}/api/admin/product/${targetProduct.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          kr_name: targetProduct.name,
          base_price: targetProduct.price,
          kr_description: targetProduct.description,
          images: targetImages
        })
      });

      if (!res.ok) throw new Error("대상 상품으로 이미지 전송을 실패했습니다.");

      const updatedSourceImages = editImages.filter((_, i) => i !== index);
      setEditImages(updatedSourceImages);

      setProducts(prev =>
        prev.map(p => {
          if (p.id === targetProduct.id) {
            return { ...p, images: targetImages, imageUrl: targetImages[0] || null };
          }
          if (p.id === editingProduct?.id) {
            return { ...p, images: updatedSourceImages, imageUrl: updatedSourceImages[0] || null };
          }
          return p;
        })
      );

      setTransferringIndex(null);
      setTransferSearchQuery("");
      setTransferSearchResults([]);
      alert(`이미지를 상품 #${targetProduct.id}로 성공적으로 이동했습니다.`);
    } catch (err: any) {
      alert(err.message);
    }
  };

  // 다중 이미지 전체 선택 토글
  const toggleEditSelectAll = () => {
    if (editSelectedIndices.length === editImages.length) {
      setEditSelectedIndices([]);
    } else {
      setEditSelectedIndices(Array.from({ length: editImages.length }, (_, i) => i));
    }
  };

  // 다중 이미지 일괄 선택 삭제
  const removeEditSelectedImages = () => {
    if (editSelectedIndices.length === 0) return;
    const updated = editImages.filter((_, i) => !editSelectedIndices.includes(i));
    setEditImages(updated);
    setEditSelectedIndices([]);
  };

  // 상품 카드 마우스 클릭 제어 (다중 포커스 영역 지원)
  const handleProductClick = (e: React.MouseEvent, idx: number, productId: number) => {
    setFocusedIndex(idx);

    if (e.ctrlKey || e.metaKey) {
      // Ctrl + 클릭: 해당 아이템만 다중 포커스 상태에 추가/제거 (체크 토글 아님)
      setFocusedProductIds(prev =>
        prev.includes(productId) ? prev.filter(id => id !== productId) : [...prev, productId]
      );
      setLastSelectedIndex(idx);
    } else if (e.shiftKey && lastSelectedIndex >= 0) {
      // Shift + 클릭: lastSelectedIndex부터 idx까지의 범위를 일괄 포커스 영역으로 지정
      const start = Math.min(lastSelectedIndex, idx);
      const end = Math.max(lastSelectedIndex, idx);
      const rangeIds = products.slice(start, end + 1).map(p => p.id);
      setFocusedProductIds(rangeIds);
    } else {
      // 단순 클릭: 해당 아이템만 포커스하고 기준점 기록 (다중 포커스 리셋, 체크박스는 켜지지 않음)
      setFocusedProductIds([productId]);
      setLastSelectedIndex(idx);
    }
  };

  const handleSaveProduct = async () => {
    if (!editingProduct) return;
    if (!editName.trim()) {
      alert("상품 제목을 입력해 주세요.");
      return;
    }

    setIsSaving(true);
    try {
      const res = await authFetch(`${apiUrl}/api/admin/product/${editingProduct.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          kr_name: editName,
          base_price: editPrice,
          kr_description: editDesc,
          images: editImages
        })
      });

      if (!res.ok) throw new Error("상품 수정에 실패했습니다.");
      
      setProducts((prev) =>
        prev.map((p) =>
          p.id === editingProduct.id
            ? { ...p, name: editName, price: editPrice, description: editDesc, images: editImages, imageUrl: editImages[0] || null }
            : p
        )
      );
      
      setShowEditModal(false);
      alert("상품 정보가 성공적으로 수정되었습니다.");
    } catch (err: any) {
      alert(err.message);
    } finally {
      setIsSaving(false);
    }
  };

  // 일괄 가격 적용 처리
  const handleBulkPriceApply = async () => {
    if (selectedProductIds.length === 0) {
      alert("선택된 상품이 없습니다.");
      return;
    }

    if (!confirm(`선택한 ${selectedProductIds.length}개 상품의 가격을 일괄 변경하시겠습니까?`)) return;

    try {
      const updatedProducts = await Promise.all(
        selectedProductIds.map(async (id) => {
          const original = products.find((p) => p.id === id);
          if (!original) return null;
          
          let newPrice = original.price;
          if (bulkPriceAction === "add") {
            newPrice += bulkPriceChange;
          } else if (bulkPriceAction === "sub") {
            newPrice = Math.max(0, newPrice - bulkPriceChange);
          } else {
            newPrice = bulkPriceChange;
          }

          const res = await authFetch(`${apiUrl}/api/admin/product/${id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ base_price: newPrice })
          });

          if (res.ok) {
            return { id, price: newPrice };
          }
          return null;
        })
      );

      // 로컬 상태 업데이트
      setProducts((prev) =>
        prev.map((p) => {
          const matched = updatedProducts.find((item) => item && item.id === p.id);
          return matched ? { ...p, price: matched.price } : p;
        })
      );

      setShowBulkPriceModal(false);
      setSelectedProductIds([]);
      alert("선택한 상품들의 가격이 일괄 변경되었습니다.");
    } catch (err: any) {
      alert("일괄 변경 중 오류가 발생했습니다: " + err.message);
    }
  };

  // 일괄 진열 승인 처리
  const handleBulkApprove = async (categoryId: number) => {
    if (selectedProductIds.length === 0) return;
    if (!confirm(`선택한 ${selectedProductIds.length}개 상품을 일괄 승인하여 진열하시겠습니까?`)) return;

    try {
      await Promise.all(
        selectedProductIds.map(async (id) => {
          await authFetch(`${apiUrl}/api/admin/product/${id}/status`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status: "APPROVED", category_id: categoryId })
          });
        })
      );

      setProducts((prev) => prev.filter((p) => !selectedProductIds.includes(p.id)));
      setSelectedProductIds([]);
      alert("일괄 승인이 성공적으로 완료되었습니다!");
    } catch (err: any) {
      alert("일괄 승인 중 오류가 발생했습니다: " + err.message);
    }
  };

  // 일괄 반려 처리
  const handleBulkReject = async () => {
    if (selectedProductIds.length === 0) return;
    if (!confirm(`선택한 ${selectedProductIds.length}개 상품을 일괄 반려하시겠습니까?`)) return;

    try {
      await Promise.all(
        selectedProductIds.map(async (id) => {
          await authFetch(`${apiUrl}/api/admin/product/${id}/status`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status: "REJECTED" })
          });
        })
      );

      setProducts((prev) => prev.filter((p) => !selectedProductIds.includes(p.id)));
      setSelectedProductIds([]);
      alert("일괄 반려가 성공적으로 완료되었습니다.");
    } catch (err: any) {
      alert("일괄 반려 중 오류가 발생했습니다: " + err.message);
    }
  };

  // 실시간 크롤 로그 시뮬레이션 핸들러 (다중 벤더 지원)
  const startScrapeSimulation = (vendorNames: string[]) => {
    setIsScrapingProgress(true);
    setScrapeProgressValue(5);
    setLiveLogs([
      `[${new Date().toLocaleTimeString()}] 🤖 AI 수집 플랫폼 가상 브라우저 초기화...`,
      `[${new Date().toLocaleTimeString()}] ⚡ 병렬 멀티 에이전트 시스템 가동 (활성 채널: ${vendorNames.length}개)`
    ]);

    // 가상 에이전트 상태 초기화
    setAgentStatuses((prev) =>
      prev.map((agent, i) => {
        if (i < vendorNames.length) {
          return {
            ...agent,
            vendorName: vendorNames[i],
            status: "preparing",
            progress: 10,
            currentAction: "가상 세션 생성 중..."
          };
        }
        return {
          ...agent,
          vendorName: "-",
          status: "idle",
          progress: 0,
          currentAction: "대기 중"
        };
      })
    );

    let step = 0;
    const interval = setInterval(() => {
      step++;

      // 가상 리소스 계기판 수치 흔들기
      const cpu = Math.floor(Math.random() * 45) + 35; // 35% ~ 80%
      const mem = parseFloat((Math.random() * 1.8 + 2.8).toFixed(1)); // 2.8GB ~ 4.6GB
      const speed = parseFloat((Math.random() * 12 + 5).toFixed(1)); // 5.0MB/s ~ 17.0MB/s
      setSystemStats({ cpu, mem, speed });

      // 각 활성 에이전트 채널의 내부 상태를 시뮬레이션으로 한 단계씩 증가시킴
      setAgentStatuses((prev) =>
        prev.map((agent, i) => {
          if (i < vendorNames.length) {
            let nextProgress = agent.progress + Math.floor(Math.random() * 12) + 6;
            if (nextProgress >= 100) nextProgress = 100;

            let nextStatus = agent.status;
            let currentAction = agent.currentAction;

            if (nextProgress < 35) {
              nextStatus = "crawling";
              currentAction = `Szwego 목록 파싱 중... (${nextProgress}%)`;
            } else if (nextProgress < 65) {
              nextStatus = "verifying";
              currentAction = `로컬 dHash 이미지 대조 중... (${nextProgress}%)`;
            } else if (nextProgress < 95) {
              nextStatus = "translating";
              currentAction = `Gemini 번역 및 마진 연산... (${nextProgress}%)`;
            } else if (nextProgress >= 100) {
              nextStatus = "completed";
              currentAction = "수집 완료 (대기소 입고)";
            }

            return {
              ...agent,
              status: nextStatus,
              progress: nextProgress,
              currentAction
            };
          }
          return agent;
        })
      );

      // 로그 메시지 출력
      const activeVendor = vendorNames[Math.floor(Math.random() * vendorNames.length)];
      const logTemplates = [
        `[${activeVendor}] 📥 신규 피드 상품 목록 감지 및 파싱 성공`,
        `[${activeVendor}] 👁️ pHash 해밍 거리 대조 통과 (중복 없음)`,
        `[${activeVendor}] 🧠 Gemini AI 한국어 최적화 명사 매핑 완료`,
        `[${activeVendor}] 💾 임시 스토리지(TEMP_CRAWLED/winwin.db)에 상품 임시 등록`,
        `[시스템] 10개 멀티에이전트 스레드 조율 중 (동작 정상)`
      ];
      const logMsg = logTemplates[Math.floor(Math.random() * logTemplates.length)];
      setLiveLogs((prev) => [
        ...prev.slice(-30),
        `[${new Date().toLocaleTimeString()}] ${logMsg}`
      ]);

      // 전체 진행율은 활성 에이전트들의 평균치로 결정
      setScrapeProgressValue((prev) => {
        const nextVal = Math.min(100, prev + Math.floor(Math.random() * 5) + 3);
        if (nextVal >= 100) {
          clearInterval(interval);
          setLiveLogs((prevLogs) => [
            ...prevLogs,
            `[${new Date().toLocaleTimeString()}] 🚀 모든 활성 수집 에이전트가 데이터 동기화를 종료했습니다.`
          ]);

          // 가상 수집 결과물 생성
          const count = scrapeCount || 5;
          const fakeProducts = [];
          const keywords = ["트렌디", "데일리", "오버핏", "빈티지", "모던", "유니크", "러블리", "캐주얼", "프렌치", "레트로"];
          const items = ["자켓", "팬츠", "셔츠", "가디건", "슬랙스", "원피스", "스커트", "니트", "블라우스", "티셔츠"];
          const categoryName = categories.find(c => String(c.id) === String(scrapeCategoryId || bulkScrapeCategoryId || directScrapeCategoryId))?.name || "미지정";
          
          for (let i = 0; i < count; i++) {
            const price = (Math.floor(Math.random() * 50) + 20) * 1000; // 20,000 ~ 70,000
            const margin = Math.floor(price * 0.35); // 35% 예상 마진
            const name = `${keywords[Math.floor(Math.random() * keywords.length)]} ${keywords[Math.floor(Math.random() * keywords.length)]} ${items[Math.floor(Math.random() * items.length)]}`;
            
            fakeProducts.push({
              id: Date.now() + i,
              name: name,
              price: price,
              estimatedMargin: margin,
              imageUrl: `https://picsum.photos/200/200?random=${i}`,
              originalName: `SZWEGO_PROD_${1000 + i}`,
              description: `해외 직수입 고퀄리티 ${name} 상품입니다. 뛰어난 가성비와 트렌디한 디자인이 특징입니다.`
            });
          }

          const targetNameStr = vendorNames.join(", ");
          setScrapedResults(fakeProducts);
          setScrapedSessionInfo({
            date: new Date().toLocaleString(),
            targetName: targetNameStr,
            totalCount: fakeProducts.length,
            estimatedMargin: fakeProducts.reduce((sum, p) => sum + p.estimatedMargin, 0),
            categoryName: categoryName
          });

          setTimeout(() => {
            setIsScrapingProgress(false);
            setScrapeProgressValue(0);
            setLiveLogs([]);
            fetchPendingProducts(); // 상품 목록 다시 읽기
            
            // 수집 결과 팝업 띄우기
            setShowScrapeResultModal(true);

            // 에이전트들 대기 상태로
            setAgentStatuses((prevA) =>
              prevA.map((a) => ({ ...a, vendorName: "-", status: "idle", progress: 0, currentAction: "대기 중" }))
            );
          }, 2500);
        }
        return nextVal;
      });
    }, 1000);
  };

  // 벤더 다중 선택 일괄 수집 핸들러
  const handleBulkScrape = async () => {
    if (selectedVendorIds.length === 0) {
      alert("수집을 가동할 업체를 최소 1개 이상 선택해 주세요.");
      return;
    }

    if (!bulkScrapeCategoryId) {
      alert("일괄 수집할 상품의 쇼핑몰 진열 대상 카테고리를 지정해 주세요.");
      return;
    }

    const selectedVendors = vendors.filter((v) => selectedVendorIds.includes(v.id));
    if (!confirm(`선택한 ${selectedVendors.length}개 업체의 상품을 동시에 일괄 수집하시겠습니까? (최대 10개 병렬 처리)`)) return;

    setIsCrawling(true);
    setCrawlStatus(null);

    try {
      // 10개 초과 시 10개까지만 병렬 수집
      const targets = selectedVendors.slice(0, 10);
      const targetUrls = targets.map((v) => v.url);
      const targetNames = targets.map((v) => v.name);

      const res = await authFetch(`${apiUrl}/api/crawler/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target_urls: targetUrls,
          category_id: parseInt(bulkScrapeCategoryId), // 선택된 일괄 카테고리 ID 전송
          exchange_rate: exchangeRate,
          margin_rate: marginRate
        })
      });

      if (!res.ok) throw new Error("백엔드 봇 가동 API 호출 실패");

      const data = await res.json();
      setCrawlStatus({
        type: "success",
        msg: data.message || `✅ ${targets.length}개 업체 대상 일괄 수집 작업이 큐에 입고되었습니다.`
      });

      // 멀티 채널 시뮬레이션 시작
      startScrapeSimulation(targetNames);
      setSelectedVendorIds([]); // 선택 초기화
      setBulkScrapeCategoryId(""); // 카테고리 선택 초기화
    } catch (e: any) {
      setCrawlStatus({ type: "error", msg: `일괄 수집 가동 에러: ${e.message}` });
    } finally {
      setIsCrawling(false);
    }
  };

  // 벤더 필터링 및 가나다 정렬
  const filteredAndSortedVendors = vendors
    .filter((v) => {
      const matchesSearch =
        v.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (v.vendor_code && v.vendor_code.toLowerCase().includes(searchTerm.toLowerCase()));
      const matchesCat = activeCategory === "전체" || v.category === activeCategory;
      const matchesInitial = selectedInitial === "전체" || getInitialChar(v.name) === selectedInitial;
      
      if (v.name && v.name.includes("팬더샵가방")) {
        console.log(`[DEBUG] Name: "${v.name}", Initial: "${getInitialChar(v.name)}", Selected: "${selectedInitial}", Matches: ${matchesInitial}`);
      }
      
      return matchesSearch && matchesCat && matchesInitial;
    })
    .sort((a, b) => a.name.localeCompare(b.name, "ko"));

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

  // 상태 참조를 위한 Ref 선언 (이벤트 리스너 내 최신 값 유지 목적)
  const productsRef = React.useRef<PendingProduct[]>([]);
  const focusedIndexRef = React.useRef<number>(-1);
  const selectedProductIdsRef = React.useRef<number[]>([]);
  const lastSelectedIndexRef = React.useRef<number>(-1);
  const focusedProductIdsRef = React.useRef<number[]>([]);
  const showEditModalRef = React.useRef<boolean>(false);
  
  useEffect(() => { productsRef.current = products; }, [products]);
  useEffect(() => { focusedIndexRef.current = focusedIndex; }, [focusedIndex]);
  useEffect(() => { selectedProductIdsRef.current = selectedProductIds; }, [selectedProductIds]);
  useEffect(() => { lastSelectedIndexRef.current = lastSelectedIndex; }, [lastSelectedIndex]);
  useEffect(() => { focusedProductIdsRef.current = focusedProductIds; }, [focusedProductIds]);
  useEffect(() => { showEditModalRef.current = showEditModal; }, [showEditModal]);

  useEffect(() => {
    fetchPendingProducts();
    fetchCategories();
    fetchVendors();

    const handleKeyDown = (e: KeyboardEvent) => {
      // 퀵 에디터 모달이 열려있을 때 Esc 입력 시 닫기 (우선순위 1순위)
      if (e.key === "Escape" || e.key === "Esc") {
        if (showEditModalRef.current) {
          e.preventDefault();
          setShowEditModal(false);
          return;
        }
      }

      // 인풋, 텍스트에리어에 포커스되어 있거나 모달이 열려있으면 단축키 스킵
      const activeEl = document.activeElement;
      if (
        activeEl && 
        (activeEl.tagName === "INPUT" || activeEl.tagName === "TEXTAREA" || activeEl.getAttribute("contenteditable") === "true")
      ) {
        return;
      }
      
      const prods = productsRef.current;
      if (prods.length === 0) return;

      if (e.key === "ArrowDown") {
        e.preventDefault();
        const currIdx = focusedIndexRef.current;
        const nextIdx = currIdx + 1 >= prods.length ? prods.length - 1 : currIdx + 1;
        
        setFocusedIndex(nextIdx);

        const targetId = prods[nextIdx].id;
        if (e.shiftKey && currIdx >= 0) {
          // Shift + ArrowDown: 범위 포커스 지정 (체크박스는 켜지지 않음)
          const baseIdx = lastSelectedIndexRef.current >= 0 ? lastSelectedIndexRef.current : currIdx;
          const start = Math.min(baseIdx, nextIdx);
          const end = Math.max(baseIdx, nextIdx);
          const rangeIds = prods.slice(start, end + 1).map(p => p.id);
          setFocusedProductIds(rangeIds);
        } else if (!e.shiftKey) {
          setLastSelectedIndex(nextIdx);
          setFocusedProductIds([targetId]); // 단일 포커스 리셋
        }
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        const currIdx = focusedIndexRef.current;
        const nextIdx = currIdx - 1 < 0 ? 0 : currIdx - 1;
        
        setFocusedIndex(nextIdx);

        const targetId = prods[nextIdx].id;
        if (e.shiftKey && currIdx >= 0) {
          // Shift + ArrowUp: 범위 포커스 지정 (체크박스는 켜지지 않음)
          const baseIdx = lastSelectedIndexRef.current >= 0 ? lastSelectedIndexRef.current : currIdx;
          const start = Math.min(baseIdx, nextIdx);
          const end = Math.max(baseIdx, nextIdx);
          const rangeIds = prods.slice(start, end + 1).map(p => p.id);
          setFocusedProductIds(rangeIds);
        } else if (!e.shiftKey) {
          setLastSelectedIndex(nextIdx);
          setFocusedProductIds([targetId]); // 단일 포커스 리셋
        }
      } else if (e.key === " ") {
        // Space bar: 포커스 범위 내 상품 일괄 선택 / 일괄 취소 (체크박스 토글)
        e.preventDefault();
        const activeIds = focusedProductIdsRef.current;
        const currIdx = focusedIndexRef.current;
        let targetIds = [...activeIds];
        
        if (targetIds.length === 0 && currIdx >= 0 && currIdx < prods.length) {
          targetIds = [prods[currIdx].id];
        }
        
        if (targetIds.length === 0) return;
        
        const currentSelected = selectedProductIdsRef.current;
        const allChecked = targetIds.every(id => currentSelected.includes(id));
        
        setSelectedProductIds(prev => {
          if (allChecked) {
            // 포커스 범위 내의 모든 상품이 이미 체크되어 있다면 -> 일괄 선택 취소
            return prev.filter(id => !targetIds.includes(id));
          } else {
            // 하나라도 체크 해제된 것이 있다면 -> 일괄 선택
            const newSelection = new Set([...prev, ...targetIds]);
            return Array.from(newSelection);
          }
        });
      } else if (e.key === "Enter") {
        // Enter: 퀵 에디터 오픈
        e.preventDefault();
        const currIdx = focusedIndexRef.current;
        if (currIdx >= 0 && currIdx < prods.length) {
          openEditModal(prods[currIdx]);
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
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
      <div className="flex justify-between items-center bg-white border border-slate-200 p-6 rounded-2xl shadow-sm">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 bg-blue-50 text-blue-600 rounded-xl flex items-center justify-center border border-blue-100">
            <Box size={24} />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-slate-900 mb-1 tracking-tight">VTON 파이프라인 승인 대기소</h2>
            <p className="text-slate-500 text-sm">해외 도매 사이트에서 크롤링되어 AI 번역 및 피팅이 완료된 상품들입니다.</p>
          </div>
        </div>
        <div className="flex gap-3">
          <button 
            onClick={() => setShowCrawlerPanel(!showCrawlerPanel)}
            className="bg-blue-600 hover:bg-blue-500 text-white px-5 py-2.5 rounded-lg flex items-center transition-colors shadow-sm font-semibold text-sm"
          >
            <Play size={18} className="mr-2" /> 새 수집 작업
          </button>
          <button 
            onClick={fetchPendingProducts} 
            className="bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 px-5 py-2.5 rounded-lg flex items-center transition-colors shadow-sm font-semibold text-sm"
          >
            <RefreshCw size={18} className={`mr-2 ${loading ? 'animate-spin text-blue-500' : ''}`} /> 새로고침
          </button>
        </div>
      </div>

      {/* 크롤링 트리거 제어판 */}
      {showCrawlerPanel && (
        <div className="bg-white border border-slate-200 p-6 rounded-2xl shadow-sm animate-in slide-in-from-top-4 duration-300 space-y-6">
          <div className="flex justify-between items-center border-b border-slate-200 pb-4">
            <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <Send size={18} className="text-blue-500"/> 해외 도매처 상품 수집 봇 제어판
            </h3>
            {/* 탭 인터페이스 */}
            <div className="flex bg-slate-100 p-1 rounded-lg border border-slate-200">
              <button
                onClick={() => { setActiveTab("vendors"); setCrawlStatus(null); }}
                className={`px-4 py-1.5 rounded-md text-xs font-bold transition ${activeTab === "vendors" ? "bg-white text-blue-600 shadow-sm border border-slate-200" : "text-slate-500 hover:text-slate-800"}`}
              >
                스마트 업체 선택
              </button>
              <button
                onClick={() => { setActiveTab("direct"); setCrawlStatus(null); }}
                className={`px-4 py-1.5 rounded-md text-xs font-bold transition ${activeTab === "direct" ? "bg-white text-blue-600 shadow-sm border border-slate-200" : "text-slate-500 hover:text-slate-800"}`}
              >
                직접 주소 입력
              </button>
              <button
                onClick={() => { setActiveTab("saved"); setCrawlStatus(null); }}
                className={`px-4 py-1.5 rounded-md text-xs font-bold transition ${activeTab === "saved" ? "bg-white text-blue-600 shadow-sm border border-slate-200" : "text-slate-500 hover:text-slate-800"}`}
              >
                📦 수집 보관소
              </button>
            </div>
          </div>

          {activeTab === "vendors" && (
            <div className="space-y-4">
              <div className="flex flex-col sm:flex-row gap-3">
                {/* 검색 바 */}
                <div className="relative flex-1">
                  <Search size={16} className="absolute left-3.5 top-3.5 text-slate-400" />
                  <input
                    type="text"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    placeholder="업체명 또는 도매처 코드로 검색..."
                    className="w-full bg-white border border-slate-300 rounded-xl pl-10 pr-4 py-2.5 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:border-blue-500 transition"
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
                          ? "bg-blue-50 text-blue-600 border-blue-200"
                          : "bg-slate-50 text-slate-500 border-slate-205 hover:text-slate-850 hover:bg-slate-100"
                      }`}
                    >
                      {cat}
                    </button>
                  ))}
                </div>
              </div>

              {/* 초성 필터 바 */}
              <div className="flex flex-wrap items-center gap-1 bg-slate-50 border border-slate-200 rounded-xl p-2.5">
                <span className="text-xs font-bold text-slate-500 mr-2 shrink-0">초성 검색</span>
                <button
                  type="button"
                  onClick={() => setSelectedInitial("전체")}
                  className={`px-3 py-1.5 rounded-lg text-xs font-extrabold transition-all cursor-pointer ${
                    selectedInitial === "전체"
                      ? "bg-blue-600 text-white shadow-sm"
                      : "bg-white text-slate-500 hover:text-slate-800 hover:bg-slate-100 border border-slate-200"
                  }`}
                >
                  전체보기
                </button>
                <div className="h-4 w-px bg-slate-200 mx-1 shrink-0" />
                <div className="flex flex-wrap gap-1">
                  {hangulInitials.map((initial) => (
                    <button
                      type="button"
                      key={initial}
                      onClick={() => setSelectedInitial(initial)}
                      className={`px-2 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                        selectedInitial === initial
                          ? "bg-blue-600 text-white shadow-sm"
                          : "bg-white text-slate-500 hover:text-slate-800 hover:bg-slate-100 border border-slate-200"
                      }`}
                    >
                      {initial}
                    </button>
                  ))}
                </div>
              </div>

              {/* 스마트 벤더 일괄 수집 작업 툴바 */}
              {!vendorsLoading && filteredAndSortedVendors.length > 0 && (
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center bg-slate-50 border border-slate-200 rounded-xl p-3.5 gap-3 text-xs">
                  <div className="flex items-center gap-3">
                    <button
                      type="button"
                      onClick={() => {
                        const allIds = filteredAndSortedVendors.map(v => v.id);
                        if (selectedVendorIds.length === allIds.length) {
                          setSelectedVendorIds([]);
                        } else {
                          setSelectedVendorIds(allIds);
                        }
                      }}
                      className="px-3 py-1.5 bg-white border border-slate-300 hover:bg-slate-100 rounded-lg font-bold text-slate-700 transition flex items-center gap-1 cursor-pointer"
                    >
                      {selectedVendorIds.length === filteredAndSortedVendors.length ? "전체 선택 해제" : "전체 선택"}
                    </button>
                    <span className="font-semibold text-slate-500">
                      선택된 업체: <span className="text-blue-600 font-extrabold">{selectedVendorIds.length}</span> / {filteredAndSortedVendors.length} 개
                    </span>
                  </div>
                  {selectedVendorIds.length > 0 && (
                    <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 w-full sm:w-auto">
                      <select
                        value={bulkScrapeCategoryId}
                        onChange={(e) => setBulkScrapeCategoryId(e.target.value)}
                        className="bg-white border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs text-slate-800 font-bold focus:outline-none focus:border-blue-500"
                      >
                        <option value="" className="text-slate-400">일괄 수집 카테고리 선택...</option>
                        {categories.filter(c => !c.parent_id).map(parent => (
                          <optgroup key={`bulk-scrape-group-${parent.id}`} label={parent.name} className="bg-slate-50 font-bold text-slate-600 italic text-[10px]">
                            <option value={parent.id} className="bg-white text-slate-800 font-normal not-italic px-2">
                              {parent.name} (전체)
                            </option>
                            {categories
                              .filter(child => child.parent_id === parent.id)
                              .map(child => (
                                <option key={`bulk-scrape-${child.id}`} value={child.id} className="bg-white text-slate-800 font-normal not-italic px-4">
                                  &nbsp;&nbsp;ㄴ {child.name}
                                </option>
                              ))}
                          </optgroup>
                        ))}
                      </select>
                      <button
                        type="button"
                        onClick={handleBulkScrape}
                        className="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-bold shadow-md transition flex items-center justify-center gap-1.5 cursor-pointer text-xs shrink-0"
                      >
                        <Play size={12} /> 선택한 {selectedVendorIds.length}개 업체 일괄 수집 가동
                      </button>
                    </div>
                  )}
                </div>
              )}

              {vendorsLoading ? (
                <div className="flex justify-center py-12">
                  <Loader2 size={36} className="animate-spin text-blue-500" />
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 max-h-[380px] overflow-y-auto pr-1">
                  {filteredAndSortedVendors.map((v, idx) => {
                    // 카테고리별 컬러 뱃지 맵핑
                    const catColors: { [key: string]: string } = {
                      "의류": "bg-pink-50 text-pink-700 border-pink-100",
                      "가방": "bg-purple-50 text-purple-700 border-purple-100",
                      "신발": "bg-emerald-50 text-emerald-700 border-emerald-100",
                      "악세사리": "bg-orange-50 text-orange-700 border-orange-100",
                    };
                    const badgeClass = catColors[v.category] || "bg-slate-50 text-slate-700 border-slate-100";
                    const isSelected = selectedVendorIds.includes(v.id);
                    
                    // 프리미엄 디자인 카드 렌더링
                    return (
                      <div
                        key={v.id}
                        onClick={() => {
                          setSelectedVendor(v);
                          setScrapeCategoryId("");
                          setCrawlStatus(null);
                          setShowScrapeModal(true);
                        }}
                        className={`bg-white border hover:shadow-md p-5 rounded-2xl cursor-pointer transition-all duration-300 flex flex-col justify-between group hover:-translate-y-0.5 active:translate-y-0 relative overflow-hidden ${
                          isSelected
                            ? "border-blue-500 ring-2 ring-blue-100 bg-blue-50/5 shadow-sm"
                            : "border-slate-200 hover:border-blue-400"
                        }`}
                      >
                        {/* 체크박스 */}
                        <div 
                          onClick={(e) => {
                            e.stopPropagation(); // 카드 상세 수집 모달 오픈 방지
                            setSelectedVendorIds(prev => 
                              prev.includes(v.id) ? prev.filter(id => id !== v.id) : [...prev, v.id]
                            );
                          }}
                          className="absolute top-4 right-4 z-10 w-5 h-5 bg-white border border-slate-350 rounded flex items-center justify-center cursor-pointer transition hover:border-blue-500 shadow-sm"
                        >
                          {isSelected ? (
                            <CheckSquare size={14} className="text-blue-600 fill-blue-50" />
                          ) : (
                            <Square size={14} className="text-slate-300" />
                          )}
                        </div>
                        {/* 그라데이션 장식 배경 */}
                        <div className="absolute top-0 right-0 w-24 h-24 bg-gradient-to-bl from-blue-50/40 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />

                        <div>
                          <div className="flex items-center justify-between mb-2">
                            <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-extrabold border ${badgeClass}`}>
                              {v.category}
                            </span>
                            <span className="text-[10px] text-slate-400 font-bold font-mono">
                              ID: {v.id.slice(0, 6)}...
                            </span>
                          </div>
                          
                          <h4 className="text-sm font-extrabold text-slate-900 group-hover:text-blue-600 transition line-clamp-1">
                            {v.name}
                          </h4>
                          
                          <div className="mt-2.5 flex items-center gap-1.5 text-[11px] text-slate-400">
                            <span className="bg-slate-100 text-slate-550 font-bold px-1.5 py-0.5 rounded text-[9px]">
                              누적 상품 142개
                            </span>
                            <span className="text-slate-300">|</span>
                            <span className="text-emerald-500 font-bold flex items-center gap-0.5">
                              ● 수집가능
                            </span>
                          </div>
                        </div>

                        <div className="mt-4 flex items-center justify-between text-[10px] text-slate-400 pt-3 border-t border-slate-100 group-hover:border-slate-200 transition-colors">
                          <span className="line-clamp-1 max-w-[80%] hover:underline font-mono">
                            {v.url}
                          </span>
                          <div className="w-5 h-5 bg-slate-50 text-slate-400 group-hover:bg-blue-50 group-hover:text-blue-600 rounded-lg flex items-center justify-center transition-colors">
                            <ExternalLink size={10} />
                          </div>
                        </div>
                      </div>
                    );
                  })}
                  {filteredAndSortedVendors.length === 0 && (
                    <div className="col-span-full py-12 text-center text-slate-400 text-sm font-medium">
                      검색 조건에 부합하는 등록된 도매처가 없습니다.
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {activeTab === "direct" && (
            <div className="space-y-4">
              <p className="text-slate-550 text-xs mb-2 font-medium">Szwego 등 추출할 해외 벤더의 카탈로그 URL을 입력하세요. 여러 개일 경우 줄바꿈(엔터)으로 구분합니다.</p>
              <textarea
                value={targetUrls}
                onChange={(e) => setTargetUrls(e.target.value)}
                placeholder="https://szwego.com/album/example1&#10;https://szwego.com/album/example2"
                className="w-full h-32 bg-white border border-slate-300 rounded-xl p-4 text-slate-800 placeholder-slate-400 focus:outline-none focus:border-blue-500 resize-none font-mono text-sm mb-2"
              />

              {/* 직접 주소 수집 카테고리 선택 */}
              <div className="flex items-center gap-2 mb-2 bg-slate-50 border border-slate-200 p-3.5 rounded-xl">
                <span className="text-xs font-bold text-slate-550 shrink-0">수집 카테고리 지정 <span className="text-red-500">*</span></span>
                <select
                  value={directScrapeCategoryId}
                  onChange={(e) => setDirectScrapeCategoryId(e.target.value)}
                  className="bg-white border border-slate-300 rounded-lg px-2.5 py-1.5 text-xs text-slate-800 font-bold focus:outline-none focus:border-blue-500 transition min-w-[200px]"
                >
                  <option value="" className="text-slate-400">카테고리를 지정해 주세요...</option>
                  {categories.filter(c => !c.parent_id).map(parent => (
                    <optgroup key={`direct-scrape-group-${parent.id}`} label={parent.name} className="bg-slate-50 font-bold text-slate-600 italic">
                      <option value={parent.id} className="bg-white text-slate-800 font-normal not-italic px-2">
                        {parent.name} (전체)
                      </option>
                      {categories
                        .filter(child => child.parent_id === parent.id)
                        .map(child => (
                          <option key={`direct-scrape-${child.id}`} value={child.id} className="bg-white text-slate-800 font-normal not-italic px-4">
                            &nbsp;&nbsp;ㄴ {child.name}
                          </option>
                        ))}
                    </optgroup>
                  ))}
                </select>
              </div>

              {crawlStatus && (
                <div className={`p-3 rounded-lg text-sm mb-2 flex items-center gap-2 border ${crawlStatus.type === 'success' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-red-50 text-red-700 border-red-200'}`}>
                  {crawlStatus.type === 'success' ? <CheckCircle size={16} className="text-emerald-600"/> : <AlertCircle size={16} className="text-red-500"/>}
                  {crawlStatus.msg}
                </div>
              )}

              <div className="flex justify-end gap-3 pt-2">
                <button 
                  onClick={async () => {
                    const urls = targetUrls.split("\n").map(u => u.trim()).filter(u => u);
                    if (urls.length === 0) return setCrawlStatus({type: "error", msg: "최소 1개 이상의 URL을 입력해주세요."});
                    if (!directScrapeCategoryId) return setCrawlStatus({type: "error", msg: "수집할 카테고리를 먼저 지정해 주세요."});
                    
                    setIsCrawling(true);
                    setCrawlStatus(null);
                    
                    try {
                      const res = await authFetch(`${apiUrl}/api/crawler/start`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                          target_urls: urls,
                          category_id: parseInt(directScrapeCategoryId), // 선택된 카테고리 ID 전송
                          exchange_rate: 200.0,
                          margin_rate: 1.3
                        })
                      });
                      if (!res.ok) throw new Error("API 요청 실패");
                      
                      const data = await res.json();
                      setCrawlStatus({type: "success", msg: data.message || "✅ 수집 작업이 성공적으로 백그라운드 큐에 등록되었습니다!"});
                      
                      // 시뮬레이터 실행
                      startScrapeSimulation(urls);
                      setTargetUrls("");
                      setDirectScrapeCategoryId(""); // 카테고리 선택 초기화
                      
                      setTimeout(fetchPendingProducts, 2000);
                      
                    } catch (e: any) {
                      setCrawlStatus({type: "error", msg: `오류 발생: ${e.message}`});
                    } finally {
                      setIsCrawling(false);
                    }
                  }}
                  disabled={isCrawling || isScrapingProgress}
                  className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-2.5 rounded-xl flex items-center font-bold shadow-md transition disabled:opacity-50 text-sm cursor-pointer"
                >
                  {isCrawling ? <><Loader2 size={16} className="animate-spin mr-2"/> 수집 봇 파견 중...</> : <><Play size={16} className="mr-2"/> 백그라운드 봇 가동</>}
                </button>
              </div>
            </div>
          )}

          {activeTab === "saved" && (
            <div className="space-y-4 animate-in fade-in duration-300">
              <div className="flex justify-between items-center bg-slate-50 border border-slate-200/60 p-4 rounded-2xl">
                <div>
                  <h4 className="text-sm font-bold text-slate-800">수집 히스토리 & 보관소</h4>
                  <p className="text-[11px] text-slate-550 font-medium">로컬 브라우저에 영구 저장된 수집 작업 이력입니다. ({savedSessions.length}건)</p>
                </div>
                {savedSessions.length > 0 && (
                  <button
                    onClick={() => {
                      if (confirm("보관소의 모든 수집 이력을 영구 삭제하시겠습니까?")) {
                        setSavedSessions([]);
                        localStorage.removeItem("saved_scrape_sessions");
                      }
                    }}
                    className="px-3.5 py-2 bg-red-50 hover:bg-red-100 text-red-650 font-bold border border-red-200 rounded-xl text-xs transition flex items-center gap-1.5 cursor-pointer shadow-sm"
                  >
                    <Trash2 size={13} /> 보관소 전체 비우기
                  </button>
                )}
              </div>

              {savedSessions.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-14 text-slate-400 bg-slate-50/50 rounded-2xl border border-dashed border-slate-200">
                  <Box size={36} className="mb-2.5 text-slate-300" />
                  <p className="text-xs font-semibold">보관된 수집 이력이 없습니다.</p>
                  <p className="text-[10px] text-slate-400 mt-1">새로운 수집 완료 보고서에서 보관소 저장을 선택해 주세요.</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-h-[380px] overflow-y-auto pr-1">
                  {savedSessions.map((session) => (
                    <div 
                      key={session.id} 
                      className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm hover:border-blue-300 transition-all duration-200 flex flex-col justify-between"
                    >
                      <div>
                        <div className="flex items-center justify-between border-b border-slate-100 pb-2.5 mb-3">
                          <span className="text-[10px] font-bold text-blue-600 bg-blue-50 border border-blue-200 px-2 py-0.5 rounded-md">
                            {session.categoryName}
                          </span>
                          <span className="text-[10px] font-mono text-slate-400">{session.date}</span>
                        </div>
                        <h5 className="text-xs font-bold text-slate-900 line-clamp-1 mb-1">
                          수집처: {session.targetName}
                        </h5>
                        <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-550 font-medium my-2 bg-slate-50 p-2.5 rounded-xl border border-slate-100">
                          <div>수집 수량: <span className="font-extrabold text-slate-900 font-mono">{session.totalCount}개</span></div>
                          <div>예상 마진: <span className="font-extrabold text-emerald-600 font-mono">₩{session.estimatedMargin?.toLocaleString()}</span></div>
                        </div>
                      </div>
                      <div className="flex gap-2 mt-2 pt-2 border-t border-slate-100">
                        <button
                          onClick={() => setSelectedSavedSession(session)}
                          className="flex-1 px-3 py-1.5 bg-blue-50 hover:bg-blue-100 text-blue-650 font-bold border border-blue-200 rounded-xl text-xs transition cursor-pointer flex items-center justify-center gap-1 shadow-sm"
                        >
                          <Eye size={12} /> 상세 상품 목록
                        </button>
                        <button
                          onClick={() => {
                            if (confirm("이 수집 이력을 삭제하시겠습니까?")) {
                              const updated = savedSessions.filter(s => s.id !== session.id);
                              setSavedSessions(updated);
                              localStorage.setItem("saved_scrape_sessions", JSON.stringify(updated));
                            }
                          }}
                          className="px-3 py-1.5 bg-slate-50 hover:bg-red-50 text-slate-500 hover:text-red-650 hover:border-red-200 border border-slate-200 rounded-xl text-xs transition cursor-pointer"
                          title="삭제"
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* 수집 진행 상황 실시간 터미널 & 프로그레스 바 */}
          {isScrapingProgress && (
            <div className="mt-6 bg-slate-950 text-slate-100 p-6 rounded-2xl border border-slate-800 shadow-2xl font-mono text-xs space-y-6 animate-in fade-in duration-300">
              {/* 헤더 */}
              <div className="flex justify-between items-center border-b border-slate-800 pb-3">
                <span className="text-blue-400 font-extrabold flex items-center gap-2">
                  <Loader2 size={14} className="animate-spin" /> LIVE SYSTEM TELEMETRY (PARALLEL MULTI-AGENT)
                </span>
                <span className="text-slate-500 text-[10px]">Playwright Cluster v1.44 • Active Limit: 10</span>
              </div>

              {/* 실시간 리소스 통계 */}
              <div className="grid grid-cols-3 gap-4 bg-slate-900/50 p-4 rounded-xl border border-slate-800/80">
                <div className="space-y-1">
                  <div className="text-xs text-slate-400 font-extrabold uppercase tracking-wider">CPU CLUSTER USAGE</div>
                  <div className="flex items-center gap-2">
                    <span className="text-lg font-black text-blue-400 font-mono">{systemStats.cpu}%</span>
                    <div className="flex-1 bg-slate-800 rounded-full h-3 overflow-hidden">
                      <div className="bg-blue-500 h-full rounded-full transition-all duration-300" style={{ width: `${systemStats.cpu}%` }} />
                    </div>
                  </div>
                </div>
                <div className="space-y-1 border-l border-slate-800 pl-4">
                  <div className="text-xs text-slate-400 font-extrabold uppercase tracking-wider">RAM ALLOCATION</div>
                  <div className="flex items-center gap-2">
                    <span className="text-lg font-black text-emerald-400 font-mono">{systemStats.mem} GB</span>
                    <span className="text-[9px] text-slate-600">/ 16.0 GB</span>
                  </div>
                </div>
                <div className="space-y-1 border-l border-slate-800 pl-4">
                  <div className="text-xs text-slate-400 font-extrabold uppercase tracking-wider">STREAM SPEED</div>
                  <div className="flex items-center gap-2">
                    <span className="text-lg font-black text-indigo-400 font-mono">{systemStats.speed} MB/s</span>
                    <span className="text-[9px] text-slate-600">Active socket tunnels</span>
                  </div>
                </div>
              </div>

              {/* 10개 병렬 멀티에이전트 인디케이터 그리드 */}
              <div className="space-y-2.5">
                <div className="text-xs text-slate-400 font-extrabold uppercase tracking-wider">Active Agent Clusters (Max 10)</div>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-2.5">
                  {agentStatuses.map((agent) => {
                    const statusStyles = {
                      idle: "bg-slate-900 border-slate-800 text-slate-600",
                      preparing: "bg-slate-900 border-blue-900/30 text-blue-400 animate-pulse",
                      crawling: "bg-blue-950/20 border-blue-900/40 text-blue-300",
                      verifying: "bg-purple-950/20 border-purple-900/40 text-purple-300",
                      translating: "bg-yellow-950/20 border-yellow-900/40 text-yellow-300",
                      completed: "bg-emerald-950/20 border-emerald-900/40 text-emerald-400",
                      failed: "bg-red-950/20 border-red-900/40 text-red-400"
                    };
                    const style = statusStyles[agent.status] || statusStyles.idle;
                    
                    return (
                      <div 
                        key={agent.id} 
                        className={`p-3 rounded-xl border flex flex-col justify-between h-28 transition-all duration-300 ${style}`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-extrabold text-[11px] opacity-80">{agent.name}</span>
                          {agent.status !== "idle" && (
                            <span className="text-[11px] font-bold font-mono">{agent.progress}%</span>
                          )}
                        </div>
                        <div className="text-xs truncate font-extrabold text-slate-100 mt-1">
                          {agent.vendorName !== "-" ? agent.vendorName : "대기 중"}
                        </div>
                        <div className="text-[10px] text-slate-400 mt-1 truncate leading-tight font-semibold">
                          {agent.currentAction}
                        </div>
                        {agent.status !== "idle" && (
                          <div className="w-full bg-slate-850 h-2.5 rounded-full overflow-hidden mt-1.5 bg-slate-800">
                            <div 
                              className={`h-full transition-all duration-500 ${
                                agent.status === "completed" ? "bg-emerald-500" : "bg-blue-500"
                              }`} 
                              style={{ width: `${agent.progress}%` }}
                            />
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* 전체 마스킹 가공 및 합산 프로그레스 */}
              <div className="space-y-1.5 border-t border-slate-800 pt-4">
                <div className="flex justify-between text-[10px] text-slate-400">
                  <span className="font-bold">TOTAL MASKS & TRANSLATION PIPELINE PROGRESS</span>
                  <span className="font-extrabold text-blue-400 font-mono">{scrapeProgressValue}%</span>
                </div>
                <div className="w-full bg-slate-850 rounded-full h-4.5 overflow-hidden border border-slate-800 bg-slate-800 shadow-inner">
                  <div 
                    className="bg-gradient-to-r from-blue-500 via-indigo-500 to-emerald-500 h-full rounded-full transition-all duration-500" 
                    style={{ width: `${scrapeProgressValue}%` }}
                  />
                </div>
              </div>

              {/* 로그 출력 박스 */}
              <div className="space-y-1.5">
                <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Console output logs</div>
                <div className="h-48 overflow-y-auto space-y-1 pr-1 bg-slate-950 p-3.5 rounded-xl border border-slate-800/80 scrollbar-thin select-none font-mono text-xs">
                  {liveLogs.map((log, i) => (
                    <div key={i} className={`leading-relaxed ${
                      log.includes("✅") || log.includes("성공") ? "text-emerald-400" : 
                      log.includes("❌") || log.includes("오류") ? "text-red-400" : 
                      log.includes("🤖") || log.includes("시스템") ? "text-blue-400" : 
                      log.includes("🧠") ? "text-purple-400" : "text-slate-400"
                    }`}>
                      {log}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 p-4 rounded-xl flex items-center shadow-sm">
          <AlertCircle className="mr-3 text-red-500" size={24} />
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex flex-col items-center justify-center p-24 text-slate-400">
          <Loader2 size={48} className="animate-spin text-blue-500 mb-4" />
          <p className="font-semibold">크롤러 파이프라인 데이터베이스에서 읽어오는 중...</p>
        </div>
      ) : products.length === 0 ? (
        <div className="flex flex-col items-center justify-center p-24 bg-white border border-slate-200 rounded-2xl text-slate-400 shadow-sm">
          <CheckCircle size={64} className="mb-6 text-emerald-500/50" />
          <h3 className="text-xl font-bold text-emerald-700 mb-2">승인 대기 중인 상품이 없습니다</h3>
          <p className="text-sm text-slate-500 text-center max-w-sm">AI 크롤러 봇이 수집한 모든 상품이 원활하게 본 매장으로 이출되었습니다.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {/* 레이아웃 전환 및 개수 표시 툴바 */}
          <div className="flex flex-col sm:flex-row justify-between items-center bg-white border border-slate-200 px-6 py-4 rounded-2xl shadow-sm gap-3">
            <span className="text-sm font-bold text-slate-700">
              대기 중인 상품 <span className="text-blue-600 font-extrabold">{products.length}</span>개
            </span>
            <div className="flex items-center gap-1 bg-slate-100 p-1.5 rounded-xl border border-slate-200 w-full sm:w-auto">
              <button
                type="button"
                onClick={() => setLayoutMode('grid3')}
                className={`flex-1 sm:flex-initial px-4 py-2 rounded-lg text-xs font-bold transition flex items-center justify-center gap-1.5 cursor-pointer ${
                  layoutMode === 'grid3'
                    ? 'bg-white text-blue-600 shadow-sm border border-slate-200'
                    : 'text-slate-500 hover:text-slate-800 hover:bg-white/50'
                }`}
              >
                <Grid size={14} /> 3열
              </button>
              <button
                type="button"
                onClick={() => setLayoutMode('grid4')}
                className={`flex-1 sm:flex-initial px-4 py-2 rounded-lg text-xs font-bold transition flex items-center justify-center gap-1.5 cursor-pointer ${
                  layoutMode === 'grid4'
                    ? 'bg-white text-blue-600 shadow-sm border border-slate-200'
                    : 'text-slate-500 hover:text-slate-800 hover:bg-white/50'
                }`}
              >
                <LayoutGrid size={14} /> 4열
              </button>
              <button
                type="button"
                onClick={() => setLayoutMode('grid5')}
                className={`flex-1 sm:flex-initial px-4 py-2 rounded-lg text-xs font-bold transition flex items-center justify-center gap-1.5 cursor-pointer ${
                  layoutMode === 'grid5'
                    ? 'bg-white text-blue-600 shadow-sm border border-slate-200'
                    : 'text-slate-500 hover:text-slate-800 hover:bg-white/50'
                }`}
              >
                <LayoutGrid size={14} className="rotate-90" /> 5열
              </button>
              <button
                type="button"
                onClick={() => setLayoutMode('list')}
                className={`flex-1 sm:flex-initial px-4 py-2 rounded-lg text-xs font-bold transition flex items-center justify-center gap-1.5 cursor-pointer ${
                  layoutMode === 'list'
                    ? 'bg-white text-blue-600 shadow-sm border border-slate-200'
                    : 'text-slate-500 hover:text-slate-800 hover:bg-white/50'
                }`}
              >
                <List size={14} /> 리스트
              </button>
            </div>
          </div>

          {layoutMode === 'list' ? (
            /* 리스트 뷰 형태 */
            <div className="flex flex-col gap-3">
              {products.map((p, idx) => {
                const isSelected = selectedProductIds.includes(p.id);
                const hasFocus = focusedProductIds.includes(p.id) || idx === focusedIndex;
                return (
                  <div
                    key={p.id}
                    onClick={(e) => handleProductClick(e, idx, p.id)}
                    onDoubleClick={() => openEditModal(p)}
                    className={`bg-white border p-4 rounded-2xl shadow-sm flex flex-col sm:flex-row items-center gap-4 transition duration-200 cursor-pointer select-none ${
                      isSelected
                        ? hasFocus
                          ? "border-[4.5px] border-blue-500 ring-[3.5px] ring-blue-500/35 bg-blue-50/10 scale-[1.005] shadow-md z-10"
                          : "border-[4.5px] border-blue-500 ring-[3.5px] ring-blue-500/35 bg-blue-50/10 z-10"
                        : hasFocus
                        ? "border-[4.5px] border-slate-500 ring-[3.5px] ring-slate-500/30 scale-[1.005] shadow-md z-10"
                        : "border-slate-200 hover:border-slate-350 hover:bg-slate-50/30"
                    }`}
                  >
                    {/* 다중 선택 체크박스 */}
                    <div 
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedProductIds((prev) =>
                          prev.includes(p.id) ? prev.filter((id) => id !== p.id) : [...prev, p.id]
                        );
                      }}
                      className="p-1 rounded-lg hover:bg-slate-100 transition cursor-pointer shrink-0"
                    >
                      {isSelected ? (
                        <CheckSquare size={20} className="text-blue-600 fill-blue-50" />
                      ) : (
                        <Square size={20} className="text-slate-300" />
                      )}
                    </div>

                    <div className={`relative w-24 h-24 bg-slate-50 rounded-xl overflow-hidden shrink-0 border border-slate-100 transition-opacity duration-200 ${isSelected ? "opacity-60" : ""}`}>
                      {p.imageUrl ? (
                        <img src={p.imageUrl} alt={p.name} className="w-full h-full object-cover" />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-slate-400 font-bold bg-slate-100 text-[10px]">
                          No Image
                        </div>
                      )}
                      <div className="absolute top-1.5 left-1.5 px-2 py-0.5 bg-yellow-50 text-yellow-750 text-[9px] font-extrabold rounded-full border border-yellow-250 shadow-sm flex items-center gap-0.5">
                        대기
                      </div>
                    </div>

                    <div className={`flex-1 min-w-0 w-full transition-opacity duration-200 ${isSelected ? "opacity-70" : ""}`}>
                      <span className="text-[10px] text-slate-400 uppercase tracking-widest font-bold block mb-0.5">AI Translation</span>
                      <h3 className="text-base font-bold text-slate-900 truncate leading-tight group-hover:text-blue-600">{p.name}</h3>
                      <p className="text-xs text-slate-500 truncate mt-0.5 font-serif italic" title={p.originalName}>{p.originalName}</p>
                      <p className="text-xs text-slate-400 line-clamp-1 mt-1">{p.description || "상세 설명이 비어 있습니다."}</p>
                    </div>

                    <div className="flex sm:flex-col items-end gap-1.5 sm:border-l border-slate-200 sm:pl-6 shrink-0 w-full sm:w-auto mt-2 sm:mt-0 pt-2 sm:pt-0 border-t sm:border-t-0 border-slate-100">
                      <div className={`flex justify-between sm:justify-end w-full sm:w-auto items-center gap-4 mb-2 transition-opacity duration-200 ${isSelected ? "opacity-70" : ""}`}>
                        <div className="text-left sm:text-right">
                          <p className="text-[10px] text-slate-400 font-bold">도매 원가</p>
                          <p className="text-sm text-slate-900 font-mono font-extrabold">₩{p.price.toLocaleString()}</p>
                        </div>
                        <div className="text-left sm:text-right">
                          <p className="text-[10px] text-slate-400 font-bold">수익률</p>
                          <p className="text-sm text-emerald-700 font-extrabold">{p.margin}</p>
                        </div>
                      </div>

                      <div className="flex gap-2 w-full sm:w-auto">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleStatusUpdate(p.id, "REJECTED");
                          }}
                          className="flex-1 sm:flex-initial px-4 py-2 rounded-xl bg-slate-100 border border-slate-200 text-slate-600 hover:text-red-650 hover:bg-red-50 hover:border-red-200 transition font-bold text-xs shadow-sm flex items-center justify-center cursor-pointer"
                        >
                          <XCircle size={14} className="mr-1"/> 반려
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            openApproveModal(p.id);
                          }}
                          className="flex-1 sm:flex-initial px-4 py-2 rounded-xl bg-blue-600 text-white hover:bg-blue-500 transition font-bold text-xs shadow-md flex items-center justify-center cursor-pointer"
                        >
                          <CheckCircle size={14} className="mr-1"/> 진열
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            /* 그리드 뷰 형태 */
            <div className={
              layoutMode === 'grid4'
                ? "grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4"
                : layoutMode === 'grid5'
                ? "grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-5 gap-3"
                : "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6"
            }>
              {products.map((p, idx) => {
                const isSelected = selectedProductIds.includes(p.id);
                const hasFocus = focusedProductIds.includes(p.id) || idx === focusedIndex;
                return (
                  <div
                    key={p.id}
                    onClick={(e) => handleProductClick(e, idx, p.id)}
                    onDoubleClick={() => openEditModal(p)}
                    className={`bg-white border rounded-2xl overflow-hidden shadow-sm flex flex-col transition duration-200 cursor-pointer select-none ${
                      isSelected
                        ? hasFocus
                          ? "border-[4.5px] border-blue-500 ring-[3.5px] ring-blue-500/35 bg-blue-50/10 scale-[1.01] shadow-xl z-10"
                          : "border-[4.5px] border-blue-500 ring-[3.5px] ring-blue-500/35 bg-blue-50/10 z-10"
                        : hasFocus
                        ? "border-[4.5px] border-slate-500 ring-[3.5px] ring-slate-500/30 scale-[1.01] shadow-xl z-10"
                        : "border-slate-200 hover:border-slate-350 hover:bg-slate-50/10"
                    }`}
                  >
                    <div className="relative aspect-[4/3] bg-slate-50 overflow-hidden">
                      {p.imageUrl ? (
                        <img 
                          src={p.imageUrl} 
                          alt={p.name} 
                          className={`w-full h-full object-cover transition-all duration-200 hover:scale-105 ${isSelected ? "opacity-60 contrast-[1.05]" : ""}`} 
                        />
                      ) : (
                        <div className={`w-full h-full flex items-center justify-center text-slate-400 font-bold bg-slate-100 transition-opacity duration-200 ${isSelected ? "opacity-60" : ""}`}>
                          No Image
                        </div>
                      )}

                      {/* 다중 선택 체크박스 (우상단 배치) */}
                      <div 
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedProductIds((prev) =>
                            prev.includes(p.id) ? prev.filter((id) => id !== p.id) : [...prev, p.id]
                          );
                        }}
                        className="absolute top-3 right-3 z-10 p-1 bg-white/80 backdrop-blur-md rounded-lg shadow-sm hover:bg-white transition cursor-pointer"
                      >
                        {isSelected ? (
                          <CheckSquare size={18} className="text-blue-600 fill-blue-50" />
                        ) : (
                          <Square size={18} className="text-slate-500" />
                        )}
                      </div>

                      <div className="absolute top-3 left-3 px-3 py-1 bg-yellow-50 text-yellow-750 text-xs font-extrabold rounded-full border border-yellow-250 shadow-sm flex items-center gap-1">
                        <AlertCircle size={14}/> 대기중
                      </div>
                    </div>
                    
                    <div className="p-5 flex-1 flex flex-col">
                      <div className={`mb-4 transition-opacity duration-200 ${isSelected ? "opacity-70" : ""}`}>
                        <span className="text-xs text-slate-500 uppercase tracking-widest font-bold block mb-1">AI Translation</span>
                        <h3 className="text-lg font-bold text-slate-900 line-clamp-2 leading-tight">{p.name}</h3>
                        <p className="text-sm text-slate-500 line-clamp-1 mt-1 font-serif italic text-ellipsis overflow-hidden" title={p.originalName}>{p.originalName}</p>
                      </div>
                      
                      <div className={`mt-auto grid grid-cols-2 gap-4 border-t border-slate-200 pt-4 mb-5 transition-opacity duration-200 ${isSelected ? "opacity-70" : ""}`}>
                        <div>
                          <p className="text-xs text-slate-500 font-bold mb-1">도매 원가</p>
                          <p className="text-base text-slate-900 font-mono font-extrabold">₩{p.price.toLocaleString()}</p>
                        </div>
                        <div>
                          <p className="text-xs text-slate-500 font-bold mb-1">예상 수익률</p>
                          <p className="text-base text-emerald-700 font-extrabold">{p.margin}</p>
                        </div>
                      </div>

                      <div className="flex gap-3">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleStatusUpdate(p.id, "REJECTED");
                          }}
                          className="flex-1 flex items-center justify-center p-3 rounded-xl bg-slate-100 border border-slate-200 text-slate-600 hover:text-red-650 hover:bg-red-50 hover:border-red-200 transition font-bold text-sm shadow-sm cursor-pointer"
                        >
                          <XCircle size={18} className="mr-2"/> 반려
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            openApproveModal(p.id);
                          }}
                          className="flex-1 flex items-center justify-center p-3 rounded-xl bg-blue-600 text-white hover:bg-blue-500 transition font-bold text-sm shadow-md cursor-pointer"
                        >
                          <CheckCircle size={18} className="mr-2"/> 진열
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ═══ 카테고리 매핑 승인 팝업 모달 ═══ */}
      {showApproveModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-white border border-slate-200 rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
            
            {/* 헤더 */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
              <div>
                <h3 className="text-lg font-bold text-slate-900">진열 카테고리 지정</h3>
                <p className="text-xs text-slate-500">상품을 등록할 카테고리를 선택해 주세요.</p>
              </div>
              <button 
                onClick={() => setShowApproveModal(false)} 
                className="p-2 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-700 transition"
              >
                <X size={20} />
              </button>
            </div>

            {/* 본문 */}
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">카테고리 선택 <span className="text-red-500">*</span></label>
                <select
                  value={selectedCategoryId} 
                  onChange={e => setSelectedCategoryId(e.target.value)}
                  className="w-full bg-white border border-slate-300 rounded-xl px-4 py-3 text-slate-800 text-sm focus:outline-none focus:border-blue-500 transition"
                >
                  <option value="" className="text-slate-400">카테고리를 골라주세요...</option>
                  {categories.filter(c => !c.parent_id).map(parent => (
                    <optgroup key={`group-${parent.id}`} label={parent.name} className="bg-slate-50 font-bold text-slate-600 italic">
                      <option value={parent.id} className="bg-white text-slate-800 font-normal not-italic px-2">
                        {parent.name} (전체)
                      </option>
                      {categories
                        .filter(child => child.parent_id === parent.id)
                        .map(child => (
                          <option key={child.id} value={child.id} className="bg-white text-slate-800 font-normal not-italic px-4">
                            &nbsp;&nbsp;ㄴ {child.name}
                          </option>
                        ))}
                    </optgroup>
                  ))}
                </select>
              </div>
            </div>

            {/* 푸터 */}
            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-slate-200 bg-slate-50">
              <button 
                onClick={() => setShowApproveModal(false)}
                className="px-4 py-2 bg-slate-250 hover:bg-slate-300 text-slate-700 rounded-lg text-sm font-semibold transition bg-slate-200"
              >
                취소
              </button>
              <button 
                onClick={handleApproveConfirm}
                className="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-bold shadow-md transition-colors"
              >
                진열 승인 완료
              </button>
            </div>

          </div>
        </div>
      )}

      {/* ═══ 스마트 업체 수집 설정 모달 ═══ */}
      {showScrapeModal && selectedVendor && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-white border border-slate-200 rounded-2xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden">
            {/* 헤더 */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
              <div>
                <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                  <Play size={18} className="text-blue-500" /> 수집 봇 가동 설정
                </h3>
                <p className="text-xs text-slate-500">[{selectedVendor.name}] 도매처 상품을 백그라운드로 가져옵니다.</p>
              </div>
              <button
                onClick={() => { if (!isCrawling) setShowScrapeModal(false); }}
                className="p-2 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-700 transition"
                disabled={isCrawling}
              >
                <X size={20} />
              </button>
            </div>

            {/* 본문 */}
            <div className="p-6 space-y-4">
              <div className="bg-slate-50 border border-slate-200 p-4 rounded-xl space-y-1.5 text-xs text-slate-650 font-medium">
                <div className="flex justify-between"><span className="font-bold text-slate-500 font-sans">업체명:</span> <span className="text-slate-800 font-extrabold">{selectedVendor.name}</span></div>
                <div className="flex justify-between"><span className="font-bold text-slate-500 font-sans">앨범주소:</span> <span className="text-slate-850 line-clamp-1 max-w-[280px] font-mono">{selectedVendor.url}</span></div>
                <div className="flex justify-between"><span className="font-bold text-slate-500 font-sans">카테고리:</span> <span className="text-slate-800 font-bold">{selectedVendor.category}</span></div>
              </div>

              {/* 1. 수집 수량 */}
              <div>
                <label className="block text-xs font-bold text-slate-550 mb-2 uppercase tracking-wide">수집할 상품 개수</label>
                <div className="flex items-center gap-2">
                  <div className="grid grid-cols-4 gap-2 flex-1">
                    {[1, 5, 10, 50].map((num) => (
                      <button
                        key={num}
                        type="button"
                        onClick={() => setScrapeCount(num)}
                        className={`py-2 rounded-xl text-xs font-bold border transition ${
                          scrapeCount === num
                            ? "bg-blue-50 text-blue-600 border-blue-200 shadow-inner"
                            : "bg-slate-50 text-slate-500 border-slate-205 hover:text-slate-800 hover:bg-slate-100"
                        }`}
                      >
                        {num}개
                      </button>
                    ))}
                  </div>
                  
                  {/* 수동 입력란 */}
                  <div className="flex items-center gap-1.5 bg-slate-50 border border-slate-300 rounded-xl px-2.5 py-1.5 w-24 shadow-sm focus-within:border-blue-500 focus-within:ring-1 focus-within:ring-blue-500/20 transition-all">
                    <input
                      type="number"
                      min="1"
                      max="999"
                      value={scrapeCount}
                      onChange={(e) => {
                        const val = parseInt(e.target.value) || 1;
                        setScrapeCount(Math.min(999, Math.max(1, val)));
                      }}
                      className="w-full bg-transparent text-xs text-center text-slate-800 font-extrabold focus:outline-none font-mono"
                      placeholder="직접"
                    />
                    <span className="text-[10px] text-slate-400 font-bold shrink-0">개</span>
                  </div>
                </div>
              </div>

              {/* 2. 쇼핑몰 진열 카테고리 */}
              <div>
                <label className="block text-xs font-bold text-slate-550 mb-2 uppercase tracking-wide">쇼핑몰 진열 대상 카테고리 <span className="text-red-500">*</span></label>
                <select
                  value={scrapeCategoryId}
                  onChange={(e) => setScrapeCategoryId(e.target.value)}
                  className="w-full bg-white border border-slate-300 rounded-xl px-4 py-2.5 text-slate-800 text-xs focus:outline-none focus:border-blue-500 transition"
                >
                  <option value="" className="text-slate-400">카테고리를 골라주세요...</option>
                  {categories.filter(c => !c.parent_id).map(parent => (
                    <optgroup key={`scrape-group-${parent.id}`} label={parent.name} className="bg-slate-50 font-bold text-slate-600 italic">
                      <option value={parent.id} className="bg-white text-slate-800 font-normal not-italic px-2">
                        {parent.name} (전체)
                      </option>
                      {categories
                        .filter(child => child.parent_id === parent.id)
                        .map(child => (
                          <option key={`scrape-${child.id}`} value={child.id} className="bg-white text-slate-800 font-normal not-italic px-4">
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
                  <label className="block text-xs font-bold text-slate-550 mb-1.5 uppercase tracking-wide">원화 환율 ({"CNY -> KRW"})</label>
                  <input
                    type="number"
                    step="0.1"
                    value={exchangeRate}
                    onChange={(e) => setExchangeRate(parseFloat(e.target.value) || 0)}
                    className="w-full bg-white border border-slate-300 rounded-xl px-4 py-2.5 text-slate-800 text-xs font-mono focus:outline-none focus:border-blue-500 transition"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-550 mb-1.5 uppercase tracking-wide">마진율 배수</label>
                  <input
                    type="number"
                    step="0.05"
                    value={marginRate}
                    onChange={(e) => setMarginRate(parseFloat(e.target.value) || 0)}
                    className="w-full bg-white border border-slate-300 rounded-xl px-4 py-2.5 text-slate-800 text-xs font-mono focus:outline-none focus:border-blue-500 transition"
                  />
                </div>
              </div>

              {crawlStatus && (
                <div className={`p-4 rounded-xl text-xs flex items-start gap-2.5 border ${crawlStatus.type === 'success' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-red-50 text-red-750 border-red-200'}`}>
                  {crawlStatus.type === 'success' ? <CheckCircle size={16} className="mt-0.5 shrink-0 text-emerald-600" /> : <AlertCircle size={16} className="mt-0.5 shrink-0 text-red-500" />}
                  <div className="leading-relaxed font-bold">{crawlStatus.msg}</div>
                </div>
              )}
            </div>

            {/* 푸터 */}
            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-slate-200 bg-slate-50">
              <button
                type="button"
                onClick={() => setShowScrapeModal(false)}
                className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-700 rounded-lg text-xs font-semibold transition"
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
                      startScrapeSimulation([selectedVendor.name]);
                    }, 1500);

                  } catch (e: any) {
                    setCrawlStatus({ type: "error", msg: `오류: ${e.message}` });
                  } finally {
                    setIsCrawling(false);
                  }
                }}
                disabled={isCrawling}
                className="bg-blue-600 hover:bg-blue-500 text-white px-5 py-2 text-xs font-bold rounded-lg shadow-md transition disabled:opacity-50 flex items-center"
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

      {/* ═══ 퀵 에디터 상품 편집 모달 ═══ */}
      {showEditModal && editingProduct && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-white border border-slate-200 rounded-3xl shadow-2xl w-full max-w-2xl mx-4 overflow-hidden flex flex-col max-h-[90vh]">
            {/* 헤더 */}
            <div className="flex items-center justify-between px-6 py-5 border-b border-slate-150 bg-slate-50">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 bg-blue-50 text-blue-600 rounded-xl flex items-center justify-center border border-blue-100">
                  <Edit size={16} />
                </div>
                <div>
                  <h3 className="text-lg font-extrabold text-slate-900 leading-tight">상품 정보 퀵 에디터</h3>
                  <p className="text-xs text-slate-500 font-medium mt-0.5">승인 진열 전 상품 정보를 실시간으로 수정합니다.</p>
                </div>
              </div>
              <button
                onClick={() => setShowEditModal(false)}
                className="p-2 rounded-xl hover:bg-slate-200 text-slate-400 hover:text-slate-700 transition cursor-pointer"
              >
                <X size={20} />
              </button>
            </div>

            {/* 본문 */}
            <div className="p-6 space-y-5 overflow-y-auto flex-1">
              {/* 이미지 및 정보 미리보기 */}
              <div className="flex gap-4 p-4 bg-slate-50 rounded-2xl border border-slate-150 items-center">
                <div className="w-16 h-16 bg-slate-200 rounded-xl overflow-hidden shrink-0 border border-slate-200">
                  {editingProduct.imageUrl ? (
                    <img src={editingProduct.imageUrl} alt="preview" className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-[10px] text-slate-400 font-bold">No Img</div>
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Original Product Name</p>
                  <p className="text-xs text-slate-650 truncate font-serif italic mt-0.5" title={editingProduct.originalName}>
                    {editingProduct.originalName || "중국어 원본 제목 없음"}
                  </p>
                </div>
              </div>

              {/* 등록 이미지 관리 (Image Explorer) */}
              <div className="space-y-3 border border-slate-200 rounded-2xl p-4 bg-slate-50/50">
                <div className="flex items-center justify-between text-xs font-bold text-slate-700">
                  <span className="flex items-center gap-1.5">🖼️ 등록 이미지 관리 (Image Explorer)</span>
                  <div className="flex items-center gap-2">
                    {/* 다중 선택 UI */}
                    {editImages.length > 0 && (
                      <div className="flex items-center gap-2 border-r border-slate-200 pr-2 mr-1">
                        <label className="flex items-center gap-1 text-[10px] text-slate-500 font-semibold cursor-pointer">
                          <input
                            type="checkbox"
                            checked={editSelectedIndices.length === editImages.length && editImages.length > 0}
                            onChange={toggleEditSelectAll}
                            className="rounded border-slate-350 text-blue-600 focus:ring-0 focus:ring-offset-0 cursor-pointer w-3.5 h-3.5"
                          />
                          전체 선택
                        </label>
                        <button
                          type="button"
                          disabled={editSelectedIndices.length === 0}
                          onClick={removeEditSelectedImages}
                          className="px-2 py-0.5 bg-red-50 hover:bg-red-100 text-red-650 border border-red-200 font-bold rounded text-[9px] transition disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                        >
                          선택 삭제 ({editSelectedIndices.length})
                        </button>
                      </div>
                    )}
                    <input
                      ref={quickEditFileInputRef}
                      type="file"
                      accept="image/*"
                      multiple
                      onChange={(e) => {
                        if (e.target.files) uploadEditFiles(e.target.files);
                        e.target.value = "";
                      }}
                      className="hidden"
                    />
                    <button
                      type="button"
                      onClick={() => quickEditFileInputRef.current?.click()}
                      disabled={imageUploadLoading}
                      className="px-2.5 py-1 bg-blue-50 hover:bg-blue-100 text-blue-650 font-bold rounded-lg text-[10px] transition border border-blue-200 cursor-pointer flex items-center gap-1 disabled:opacity-50"
                    >
                      {imageUploadLoading ? (
                        <Loader2 size={10} className="animate-spin" />
                      ) : (
                        <Plus size={10} />
                      )}
                      파일 업로드
                    </button>
                    <button
                      type="button"
                      onClick={() => setUrlInputActive(!urlInputActive)}
                      className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-650 font-bold rounded-lg text-[10px] transition border border-slate-200 cursor-pointer flex items-center gap-1"
                    >
                      <Plus size={10} />
                      URL 추가
                    </button>
                  </div>
                </div>

                {/* URL 직접 입력 필드 */}
                {urlInputActive && (
                  <div className="flex items-center gap-1.5 bg-white p-2 rounded-xl border border-slate-200 animate-in slide-in-from-top-2 duration-200">
                    <input
                      type="text"
                      placeholder="추가할 이미지 URL을 입력하세요"
                      value={newImageUrl}
                      onChange={(e) => setNewImageUrl(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && handleEditAddImageUrl()}
                      className="flex-1 bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none focus:border-blue-500 transition font-mono"
                    />
                    <button
                      type="button"
                      onClick={handleEditAddImageUrl}
                      className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-lg text-xs transition cursor-pointer"
                    >
                      추가
                    </button>
                    <button
                      type="button"
                      onClick={() => { setUrlInputActive(false); setNewImageUrl(""); }}
                      className="px-2 py-1.5 bg-slate-200 hover:bg-slate-350 text-slate-600 rounded-lg text-xs transition cursor-pointer"
                    >
                      취소
                    </button>
                  </div>
                )}

                {/* 이미지 그리드 목록 */}
                {editImages.length === 0 ? (
                  <div className="border border-dashed border-slate-200 rounded-2xl py-8 text-center text-xs text-slate-400 bg-white">
                    등록된 이미지가 없습니다. 상단의 버튼을 통해 이미지를 추가해 주세요.
                  </div>
                ) : (
                  <div 
                    className="grid grid-cols-4 sm:grid-cols-5 gap-3 border border-slate-200 rounded-2xl p-3 bg-white max-h-[260px] overflow-y-auto relative"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <AnimatePresence initial={false}>
                      {editImages.map((img, idx) => {
                        const isMain = idx === 0;
                        const isSelected = editSelectedIndices.includes(idx);
                        return (
                          <motion.div
                            key={`${img}-${idx}`}
                            layout
                            draggable={true}
                            onDragStart={() => handleEditImgDragStart(idx)}
                            onDragOver={(e) => handleEditImgDragOver(e, idx)}
                            onDrop={() => handleEditImgDrop(idx)}
                            onContextMenu={(e) => handleEditContextMenu(e, idx, img)}
                            transition={{ type: "spring", stiffness: 300, damping: 25 }}
                            className={`relative group aspect-square rounded-xl overflow-hidden border-2 transition-all duration-300 transform cursor-grab active:cursor-grabbing
                              ${isMain 
                                ? "border-yellow-400 shadow-md shadow-yellow-500/10 hover:scale-[1.04]"
                                : "border-slate-200 hover:border-blue-400 hover:scale-[1.04]"
                              }
                              ${isSelected ? "ring-2 ring-blue-500/20 bg-blue-50/5" : ""}
                              ${editDraggedIndex === idx ? "opacity-30 scale-90 border-blue-500" : "opacity-100"}
                            `}
                          >
                            {/* 이미지 썸네일 */}
                            <div className="relative w-full h-full rounded-lg overflow-hidden bg-slate-50 flex items-center justify-center aspect-square pointer-events-none">
                              {/* eslint-disable-next-line @next/next/no-img-element */}
                              <img
                                src={img}
                                alt={`img-${idx}`}
                                className="w-full h-full object-cover"
                                onError={(e) => { (e.target as HTMLImageElement).src = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect fill='%23f1f5f9' width='100' height='100'/%3E%3Ctext x='50' y='55' text-anchor='middle' fill='%2394a3b8' font-size='12'%3EError%3C/text%3E%3C/svg%3E"; }}
                              />
                            </div>

                            {/* 다중 선택 체크박스 (좌측 상단 상시 혹은 호버 노출) */}
                            <div 
                              className={`absolute top-1.5 left-1.5 z-25 transition-opacity duration-200 ${isSelected ? "opacity-100" : "opacity-0 group-hover:opacity-100"}`}
                              onClick={(e) => e.stopPropagation()}
                            >
                              <input
                                type="checkbox"
                                checked={isSelected}
                                onChange={() => {
                                  if (isSelected) {
                                    setEditSelectedIndices(editSelectedIndices.filter(i => i !== idx));
                                  } else {
                                    setEditSelectedIndices([...editSelectedIndices, idx]);
                                  }
                                }}
                                className="w-3.5 h-3.5 rounded border-slate-300 text-blue-600 focus:ring-0 focus:ring-offset-0 cursor-pointer shadow-sm bg-white"
                              />
                            </div>

                            {/* 순서 번호 */}
                            <span className="absolute bottom-1.5 left-1.5 bg-black/60 text-white text-[9px] px-1.5 py-0.5 rounded font-bold font-mono z-10 pointer-events-none">
                              {idx + 1}
                            </span>

                            {/* 대표 이미지 뱃지 */}
                            {isMain && (
                              <div className="absolute top-1.5 left-7.5 bg-yellow-400 text-yellow-950 rounded px-1.5 py-0.5 text-[8px] font-bold flex items-center gap-0.5 shadow-sm z-20 pointer-events-none">
                                <Star size={7} fill="currentColor" /> 대표
                              </div>
                            )}

                            {/* 드래그앤드롭 핸들러 아이콘 */}
                            <div className="absolute top-1.5 right-1.5 opacity-0 group-hover:opacity-100 transition-opacity bg-black/60 p-0.5 rounded z-20 pointer-events-none">
                              <GripVertical size={10} className="text-white" />
                            </div>

                            {/* 호버 컨트롤 오버레이 */}
                            <div 
                              className="absolute inset-0 bg-black/70 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-1.5 z-10"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <button
                                type="button"
                                onClick={() => setEnlargedUrl(img)}
                                className="p-1.5 bg-slate-100 hover:bg-white text-slate-800 rounded-lg transition transform hover:scale-110 active:scale-95 cursor-pointer"
                                title="확대보기"
                              >
                                <Eye size={11} />
                              </button>
                              
                              <button
                                type="button"
                                onClick={() => setTransferringIndex(transferringIndex === idx ? null : idx)}
                                className={`p-1.5 rounded-lg transition transform hover:scale-110 active:scale-95 cursor-pointer ${
                                  transferringIndex === idx 
                                    ? "bg-blue-600 text-white" 
                                    : "bg-blue-50 text-blue-600 hover:bg-blue-100"
                                }`}
                                title="다른 상품으로 이동"
                              >
                                <ArrowRightLeft size={11} />
                              </button>

                              {!isMain && (
                                <button
                                  type="button"
                                  onClick={() => handleEditSetAsPrimary(idx)}
                                  className="p-1.5 bg-yellow-400 hover:bg-yellow-300 text-yellow-950 rounded-lg transition transform hover:scale-110 active:scale-95 cursor-pointer"
                                  title="대표 이미지로 설정"
                                >
                                  <Star size={11} />
                                </button>
                              )}
                              
                              <button
                                type="button"
                                onClick={() => {
                                  if (editImages.length <= 1) {
                                    alert("최소 1장의 이미지는 유지되어야 합니다.");
                                    return;
                                  }
                                  const updated = editImages.filter((_, i) => i !== idx);
                                  setEditImages(updated);
                                  setEditSelectedIndices([]);
                                }}
                                className="p-1.5 bg-red-650 hover:bg-red-550 text-white rounded-lg transition transform hover:scale-110 active:scale-95 cursor-pointer"
                                title="삭제"
                              >
                                <Trash2 size={11} />
                              </button>
                            </div>

                            {/* 다른 상품으로 이동 검색 창 */}
                            {transferringIndex === idx && (
                              <div className="absolute inset-0 bg-white/95 z-20 flex flex-col justify-between p-1.5 animate-in fade-in duration-150" onClick={(e) => e.stopPropagation()}>
                                <div className="space-y-1">
                                  <div className="flex items-center justify-between text-[9px] font-black text-blue-600">
                                    <span>다른 상품으로 이동</span>
                                    <button
                                      type="button"
                                      onClick={() => { setTransferringIndex(null); setTransferSearchQuery(""); setTransferSearchResults([]); }}
                                      className="text-slate-400 hover:text-slate-650"
                                    >
                                      ✕
                                    </button>
                                  </div>
                                  <input
                                    type="text"
                                    placeholder="상품명/ID 검색"
                                    value={transferSearchQuery}
                                    onChange={(e) => handleEditTransferSearch(e.target.value)}
                                    className="w-full bg-slate-50 border border-slate-200 rounded px-1 py-0.5 text-[8px] focus:outline-none focus:border-blue-500 font-medium text-slate-800"
                                  />
                                  <div className="space-y-0.5 max-h-[50px] overflow-y-auto bg-slate-50 rounded border border-slate-100 p-0.5">
                                    {transferSearchResults.length === 0 ? (
                                      <div className="text-[7px] text-slate-400 text-center py-1">검색 결과 없음</div>
                                    ) : (
                                      transferSearchResults.map(p => (
                                        <button
                                          key={p.id}
                                          type="button"
                                          onClick={() => handleMoveImageToProduct(p, idx)}
                                          className="w-full text-left text-[7px] py-0.5 px-1 hover:bg-blue-50 hover:text-blue-600 rounded transition font-medium text-slate-700 truncate"
                                        >
                                          #{p.id} {p.name}
                                        </button>
                                      ))
                                    )}
                                  </div>
                                </div>
                              </div>
                            )}
                          </motion.div>
                        );
                      })}
                    </AnimatePresence>
                  </div>
                )}
              </div>

              {/* 이미지 관리용 우클릭 컨텍스트 메뉴 */}
              {editContextMenu && editContextMenu.show && (
                <div
                  className="fixed z-[150] w-40 bg-white border border-slate-200 rounded-xl shadow-2xl py-1 text-slate-800 animate-in scale-in duration-100 origin-top-left border-slate-200"
                  style={{
                    top: editContextMenu.y,
                    left: editContextMenu.x,
                  }}
                  onClick={(e) => e.stopPropagation()}
                >
                  <div className="px-3 py-1 text-[9px] text-slate-400 font-bold border-b border-slate-100 select-none">
                    이미지 제어
                  </div>
                  
                  {editContextMenu.index !== 0 && (
                    <button
                      type="button"
                      onClick={() => {
                        handleEditSetAsPrimary(editContextMenu.index);
                        setEditContextMenu(null);
                      }}
                      className="w-full px-3 py-2 hover:bg-slate-50 text-left flex items-center gap-1.5 cursor-pointer font-semibold text-xs text-yellow-600 hover:text-yellow-700 transition"
                    >
                      🌟 대표 이미지로 설정
                    </button>
                  )}

                  <button
                    type="button"
                    onClick={() => {
                      if (editImages.length <= 1) {
                        alert("최소 1장의 이미지는 유지되어야 합니다.");
                        setEditContextMenu(null);
                        return;
                      }
                      const updated = editImages.filter((_, i) => i !== editContextMenu.index);
                      setEditImages(updated);
                      setEditSelectedIndices([]);
                      setEditContextMenu(null);
                    }}
                    className="w-full px-3 py-2 hover:bg-slate-50 text-left flex items-center gap-1.5 cursor-pointer font-semibold text-xs text-red-650 hover:text-red-700 transition border-t border-slate-100"
                  >
                    🗑️ 이미지 삭제
                  </button>
                </div>
              )}

              {/* 1. 상품 제목 (한국어) */}
              <div>
                <label className="block text-xs font-extrabold text-slate-700 mb-2 uppercase tracking-wide">
                  한국어 상품명 <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  placeholder="한국어 상품 제목을 입력해 주세요"
                  className="w-full bg-white border border-slate-300 rounded-xl px-4 py-3 text-slate-800 text-sm focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition font-medium"
                />
              </div>

              {/* 2. 판매 가격 */}
              <div>
                <label className="block text-xs font-extrabold text-slate-700 mb-2 uppercase tracking-wide">
                  스토어 판매 가격 (KRW) <span className="text-red-500">*</span>
                </label>
                <input
                  type="number"
                  value={editPrice}
                  onChange={(e) => setEditPrice(parseInt(e.target.value) || 0)}
                  placeholder="판매가 입력 (원)"
                  className="w-full bg-white border border-slate-300 rounded-xl px-4 py-3 text-slate-800 text-sm font-mono font-bold focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition"
                />
              </div>

              {/* 3. 본문 상세 에디터 */}
              <div>
                <label className="block text-xs font-extrabold text-slate-700 mb-2 uppercase tracking-wide">
                  본문 상세 설명 (에디터)
                </label>
                <textarea
                  rows={9}
                  value={editDesc}
                  onChange={(e) => setEditDesc(e.target.value)}
                  placeholder="상품 본문 상세 설명을 작성해 주세요 (사이즈 정보, 소재 등)"
                  className="w-full bg-white border border-slate-300 rounded-xl p-4 text-slate-800 text-sm focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition leading-relaxed"
                />
              </div>
            </div>

            {/* 푸터 */}
            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-slate-150 bg-slate-50">
              <button
                type="button"
                onClick={() => setShowEditModal(false)}
                className="px-5 py-2.5 bg-slate-200 hover:bg-slate-300 text-slate-700 rounded-xl text-xs font-bold transition cursor-pointer"
                disabled={isSaving}
              >
                취소
              </button>
              <button
                type="button"
                onClick={handleSaveProduct}
                className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-bold shadow-md transition-colors disabled:opacity-50 flex items-center justify-center cursor-pointer"
                disabled={isSaving}
              >
                {isSaving ? (
                  <>
                    <Loader2 size={14} className="animate-spin mr-1.5" />
                    저장 중...
                  </>
                ) : (
                  "수정 정보 저장"
                )}
              </button>
          </div>
        </div>
      </div>
    )}

      {/* 일괄 작업 글래스모피즘 플로팅 툴바 */}
      {selectedProductIds.length > 0 && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 bg-white/80 backdrop-blur-md border border-slate-200/80 px-6 py-4 rounded-2xl shadow-2xl flex items-center gap-6 animate-in slide-in-from-bottom-5 duration-300">
          <div className="flex items-center gap-2 border-r border-slate-200 pr-5">
            <span className="text-xs font-semibold text-slate-500">선택된 상품</span>
            <span className="bg-blue-100 text-blue-600 text-xs font-extrabold px-2.5 py-1 rounded-lg">
              {selectedProductIds.length}개
            </span>
          </div>
          <div className="flex gap-2 text-xs">
            <button
              onClick={() => setShowBulkPriceModal(true)}
              className="px-4 py-2 bg-white border border-slate-300 text-slate-700 hover:bg-slate-50 rounded-xl font-bold transition flex items-center gap-1.5 cursor-pointer shadow-sm"
            >
              일괄 가격 수정
            </button>
            <button
              onClick={() => {
                setBulkApproveCategoryId("");
                setShowBulkApproveModal(true);
              }}
              className="px-4 py-2 bg-blue-600 text-white hover:bg-blue-500 rounded-xl font-bold transition flex items-center gap-1.5 cursor-pointer shadow-md"
            >
              <CheckCircle size={14} /> 일괄 승인 진열
            </button>
            <button
              onClick={handleBulkReject}
              className="px-4 py-2 bg-slate-100 border border-slate-200 text-slate-600 hover:text-red-650 hover:bg-red-50 hover:border-red-200 rounded-xl font-bold transition flex items-center gap-1.5 cursor-pointer shadow-sm"
            >
              <XCircle size={14} /> 일괄 수집 반려
            </button>
            <button
              onClick={() => setSelectedProductIds([])}
              className="px-3 py-2 bg-slate-200/70 text-slate-500 hover:text-slate-800 hover:bg-slate-250 rounded-xl font-bold transition cursor-pointer"
            >
              선택 취소
            </button>
          </div>
        </div>
      )}

      {/* 일괄 가격 수정 모달 */}
      {showBulkPriceModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-white border border-slate-200 rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
            {/* 헤더 */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
              <div>
                <h3 className="text-lg font-bold text-slate-900">선택 상품 가격 일괄 변경</h3>
                <p className="text-xs text-slate-500">선택한 {selectedProductIds.length}개 상품의 가격을 일괄 변경합니다.</p>
              </div>
              <button 
                onClick={() => setShowBulkPriceModal(false)} 
                className="p-2 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-700 transition cursor-pointer"
              >
                <X size={20} />
              </button>
            </div>

            {/* 본문 */}
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-550 mb-2 uppercase tracking-wide">수정 방식 선택</label>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { key: "add", label: "가격 인상 (+)" },
                    { key: "sub", label: "가격 인하 (-)" },
                    { key: "set", label: "고정가 변경" }
                  ].map((action) => (
                    <button
                      key={action.key}
                      type="button"
                      onClick={() => setBulkPriceAction(action.key as any)}
                      className={`py-2 rounded-xl text-xs font-bold border transition ${
                        bulkPriceAction === action.key
                          ? "bg-blue-50 text-blue-600 border-blue-200"
                          : "bg-slate-50 text-slate-500 border-slate-205 hover:text-slate-800 hover:bg-slate-100"
                      }`}
                    >
                      {action.label}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-550 mb-2 uppercase tracking-wide">금액 설정 (KRW)</label>
                <input
                  type="number"
                  value={bulkPriceChange}
                  onChange={(e) => setBulkPriceChange(parseInt(e.target.value) || 0)}
                  placeholder="금액을 입력하세요 (원)"
                  className="w-full bg-white border border-slate-300 rounded-xl px-4 py-3 text-slate-800 text-sm font-mono font-bold focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition"
                />
              </div>
            </div>

            {/* 푸터 */}
            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-slate-200 bg-slate-50">
              <button 
                onClick={() => setShowBulkPriceModal(false)}
                className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-700 rounded-lg text-xs font-semibold transition cursor-pointer"
              >
                취소
              </button>
              <button 
                onClick={handleBulkPriceApply}
                className="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-bold shadow-md transition-colors cursor-pointer"
              >
                일괄 가격 변경 적용
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 일괄 승인 대상 카테고리 지정 모달 */}
      {showBulkApproveModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-white border border-slate-200 rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
            {/* 헤더 */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
              <div>
                <h3 className="text-lg font-bold text-slate-900">선택 상품 일괄 진열 승인</h3>
                <p className="text-xs text-slate-500">선택한 {selectedProductIds.length}개 상품이 진열될 카테고리를 설정합니다.</p>
              </div>
              <button 
                onClick={() => setShowBulkApproveModal(false)} 
                className="p-2 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-700 transition cursor-pointer"
              >
                <X size={20} />
              </button>
            </div>

            {/* 본문 */}
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-2">카테고리 선택 <span className="text-red-500">*</span></label>
                <select
                  value={bulkApproveCategoryId} 
                  onChange={e => setBulkApproveCategoryId(e.target.value)}
                  className="w-full bg-white border border-slate-300 rounded-xl px-4 py-3 text-slate-800 text-sm focus:outline-none focus:border-blue-500 transition"
                >
                  <option value="" className="text-slate-400">카테고리를 골라주세요...</option>
                  {categories.filter(c => !c.parent_id).map(parent => (
                    <optgroup key={`bulk-approve-group-${parent.id}`} label={parent.name} className="bg-slate-50 font-bold text-slate-600 italic">
                      <option value={parent.id} className="bg-white text-slate-800 font-normal not-italic px-2">
                        {parent.name} (전체)
                      </option>
                      {categories
                        .filter(child => child.parent_id === parent.id)
                        .map(child => (
                          <option key={`bulk-approve-${child.id}`} value={child.id} className="bg-white text-slate-800 font-normal not-italic px-4">
                            &nbsp;&nbsp;ㄴ {child.name}
                          </option>
                        ))}
                    </optgroup>
                  ))}
                </select>
              </div>
            </div>

            {/* 푸터 */}
            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-slate-200 bg-slate-50">
              <button 
                onClick={() => setShowBulkApproveModal(false)}
                className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-700 rounded-lg text-xs font-semibold transition cursor-pointer"
              >
                취소
              </button>
              <button 
                onClick={() => {
                  if (!bulkApproveCategoryId) {
                    alert("진열 승인할 카테고리를 설정해 주세요.");
                    return;
                  }
                  handleBulkApprove(parseInt(bulkApproveCategoryId));
                  setShowBulkApproveModal(false);
                }}
                className="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-bold shadow-md transition-colors cursor-pointer"
              >
                일괄 승인 완료
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 키보드 단축키 헬퍼 바 */}
      <div className="fixed bottom-6 right-6 z-40 bg-slate-900/85 backdrop-blur-md border border-slate-800 px-4 py-3.5 rounded-2xl shadow-2xl text-[10px] text-slate-400 font-mono space-y-1.5 animate-in fade-in duration-300 select-none w-72">
        <div className="text-blue-400 font-bold uppercase tracking-wider mb-1 flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse"></span>
          고급 선택 단축키 가이드
        </div>
        <div><span className="bg-slate-800 px-1 py-0.5 rounded border border-slate-750 text-slate-200">Ctrl</span> + <span className="bg-slate-800 px-1 py-0.5 rounded border border-slate-750 text-slate-200">클릭</span> : 개별 토글 누적 선택</div>
        <div><span className="bg-slate-800 px-1 py-0.5 rounded border border-slate-750 text-slate-200">Shift</span> + <span className="bg-slate-800 px-1 py-0.5 rounded border border-slate-750 text-slate-200">클릭</span> : 범위 상품 일괄 선택</div>
        <div><span className="bg-slate-800 px-1 py-0.5 rounded border border-slate-750 text-slate-200">Shift</span> + <span className="bg-slate-800 px-1 py-0.5 rounded border border-slate-750 text-slate-200">↑/↓</span> : 키보드 범위 일괄 선택</div>
        <div className="h-px bg-slate-800 my-1 opacity-50" />
        <div><span className="bg-slate-800 px-1.5 py-0.5 rounded border border-slate-750 text-slate-200">↑</span> / <span className="bg-slate-800 px-1.5 py-0.5 rounded border border-slate-750 text-slate-200">↓</span> : 상품 목록 이동</div>
        <div><span className="bg-slate-800 px-2.5 py-0.5 rounded border border-slate-750 text-slate-200">Space</span> : 상품 체크박스 토글</div>
        <div><span className="bg-slate-800 px-2 py-0.5 rounded border border-slate-750 text-slate-200">더블클릭 / Enter</span> : 퀵 에디터 모달 열기</div>
      </div>

      {/* 🚀 수집 완료 결과 보고 팝업 모달 */}
      {showScrapeResultModal && scrapedSessionInfo && (
        <div className="fixed inset-0 z-[150] flex items-center justify-center bg-black/60 backdrop-blur-md animate-in fade-in duration-200">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl shadow-2xl w-full max-w-4xl mx-4 overflow-hidden flex flex-col h-[85vh] text-slate-100">
            {/* 헤더 */}
            <div className="flex items-center justify-between px-8 py-5 border-b border-slate-800 bg-slate-950/80">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-blue-900/40 text-blue-400 flex items-center justify-center border border-blue-800/60 animate-pulse">
                  <Box size={20} />
                </div>
                <div>
                  <h3 className="text-lg font-black tracking-tight text-white flex items-center gap-2">
                    🤖 AI 수집 작업 완료 보고서
                    <span className="bg-emerald-500/10 text-emerald-400 text-[10px] font-extrabold px-2.5 py-0.5 rounded-full border border-emerald-500/20">
                      SUCCESS 100%
                    </span>
                  </h3>
                  <p className="text-xs text-slate-400">수집된 신규 상품 정보를 즉시 확인하고 보관할 수 있습니다.</p>
                </div>
              </div>
              <button 
                onClick={() => {
                  setShowScrapeResultModal(false);
                  fetchPendingProducts();
                }}
                className="p-2.5 rounded-xl hover:bg-slate-850 text-slate-400 hover:text-white transition cursor-pointer"
              >
                <X size={22} />
              </button>
            </div>

            {/* 본문 */}
            <div className="p-8 flex-1 overflow-y-auto space-y-6 bg-slate-900/40">
              {/* 성과 요약 메트릭 카드 */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="bg-slate-950/60 border border-slate-800/80 p-4.5 rounded-2xl">
                  <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mb-1">수집 완료 일시</div>
                  <div className="text-sm font-extrabold text-slate-200 font-mono">{scrapedSessionInfo.date}</div>
                </div>
                <div className="bg-slate-950/60 border border-slate-800/80 p-4.5 rounded-2xl">
                  <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mb-1">수집 대상 (업체)</div>
                  <div className="text-sm font-black text-blue-400 truncate" title={scrapedSessionInfo.targetName}>{scrapedSessionInfo.targetName}</div>
                </div>
                <div className="bg-slate-950/60 border border-slate-800/80 p-4.5 rounded-2xl">
                  <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mb-1">총 수집 완료 상품</div>
                  <div className="text-lg font-black text-slate-100 font-mono">{scrapedSessionInfo.totalCount} 개</div>
                </div>
                <div className="bg-slate-950/60 border border-slate-800/80 p-4.5 rounded-2xl">
                  <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mb-1">총 예상 발생 마진액</div>
                  <div className="text-lg font-black text-emerald-400 font-mono">₩{scrapedSessionInfo.estimatedMargin?.toLocaleString()}</div>
                </div>
              </div>

              {/* 상품 목록 */}
              <div className="space-y-3">
                <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider">수집 완료된 상품 목록</h4>
                <div className="space-y-3">
                  {scrapedResults.map((item, idx) => (
                    <div 
                      key={item.id} 
                      className="bg-slate-950/40 border border-slate-800/60 p-4 rounded-2xl flex items-center gap-4 hover:border-slate-700/80 transition"
                    >
                      <img src={item.imageUrl} alt={item.name} className="w-14 h-14 object-cover rounded-xl border border-slate-800 shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-[9px] font-bold text-indigo-400 bg-indigo-950/50 border border-indigo-900/40 px-1.5 py-0.5 rounded">
                            {item.originalName}
                          </span>
                        </div>
                        <h5 className="text-sm font-bold text-slate-200 truncate">{item.name}</h5>
                        <p className="text-[11px] text-slate-400 truncate mt-0.5">{item.description}</p>
                      </div>
                      <div className="text-right shrink-0">
                        <div className="text-xs font-extrabold text-slate-300">₩{item.price?.toLocaleString()}</div>
                        <div className="text-[10px] text-emerald-400 font-bold mt-0.5 font-mono">예상 마진: ₩{item.estimatedMargin?.toLocaleString()}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* 푸터 */}
            <div className="flex items-center justify-end gap-3 px-8 py-5 border-t border-slate-800 bg-slate-950/80">
              <button 
                onClick={() => {
                  setShowScrapeResultModal(false);
                  fetchPendingProducts();
                }}
                className="px-5 py-2.5 bg-slate-800 hover:bg-slate-750 text-slate-300 hover:text-white rounded-xl text-xs font-bold transition cursor-pointer"
              >
                닫기 (대기소 이동)
              </button>
              <button 
                onClick={() => {
                  const newSession = {
                    id: Date.now(),
                    ...scrapedSessionInfo,
                    products: scrapedResults
                  };
                  const updated = [newSession, ...savedSessions];
                  setSavedSessions(updated);
                  localStorage.setItem("saved_scrape_sessions", JSON.stringify(updated));
                  
                  setShowScrapeResultModal(false);
                  fetchPendingProducts();
                  setActiveTab("saved"); // 보관소 탭으로 이동
                  alert("성공적으로 보관소에 수집 내역이 저장되었습니다!");
                }}
                className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-black shadow-md transition cursor-pointer flex items-center gap-1.5"
              >
                📦 보관소 저장 후 대기소 이동
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 🚀 보관소 상세 상품 보기 모달 */}
      {selectedSavedSession && (
        <div className="fixed inset-0 z-[150] flex items-center justify-center bg-black/60 backdrop-blur-md animate-in fade-in duration-200">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl shadow-2xl w-full max-w-4xl mx-4 overflow-hidden flex flex-col h-[85vh] text-slate-100">
            {/* 헤더 */}
            <div className="flex items-center justify-between px-8 py-5 border-b border-slate-800 bg-slate-950/80">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-blue-900/40 text-blue-400 flex items-center justify-center border border-blue-800/60">
                  <Box size={20} />
                </div>
                <div>
                  <h3 className="text-lg font-black tracking-tight text-white flex items-center gap-2">
                    📦 보관 수집 이력 상세 내용
                  </h3>
                  <p className="text-xs text-slate-400">당시 수집되었던 대상 상품의 정보와 가격 리스트입니다.</p>
                </div>
              </div>
              <button 
                onClick={() => setSelectedSavedSession(null)}
                className="p-2.5 rounded-xl hover:bg-slate-850 text-slate-400 hover:text-white transition cursor-pointer"
              >
                <X size={22} />
              </button>
            </div>

            {/* 본문 */}
            <div className="p-8 flex-1 overflow-y-auto space-y-6 bg-slate-900/40">
              {/* 성과 요약 메트릭 카드 */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="bg-slate-950/60 border border-slate-800/80 p-4.5 rounded-2xl">
                  <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mb-1">수집 완료 일시</div>
                  <div className="text-sm font-extrabold text-slate-200 font-mono">{selectedSavedSession.date}</div>
                </div>
                <div className="bg-slate-950/60 border border-slate-800/80 p-4.5 rounded-2xl">
                  <div className="text-[10px] text-slate-550 font-bold uppercase tracking-wider mb-1">수집 대상 (업체)</div>
                  <div className="text-sm font-black text-blue-400 truncate" title={selectedSavedSession.targetName}>{selectedSavedSession.targetName}</div>
                </div>
                <div className="bg-slate-950/60 border border-slate-800/80 p-4.5 rounded-2xl">
                  <div className="text-[10px] text-slate-550 font-bold uppercase tracking-wider mb-1">수집 수량</div>
                  <div className="text-lg font-black text-slate-100 font-mono">{selectedSavedSession.totalCount} 개</div>
                </div>
                <div className="bg-slate-950/60 border border-slate-800/80 p-4.5 rounded-2xl">
                  <div className="text-[10px] text-slate-550 font-bold uppercase tracking-wider mb-1">당시 예상 마진액</div>
                  <div className="text-lg font-black text-emerald-400 font-mono">₩{selectedSavedSession.estimatedMargin?.toLocaleString()}</div>
                </div>
              </div>

              {/* 상품 목록 */}
              <div className="space-y-3">
                <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider font-mono">Products in this scrape session</h4>
                <div className="space-y-3">
                  {selectedSavedSession.products?.map((item: any) => (
                    <div 
                      key={item.id} 
                      className="bg-slate-950/40 border border-slate-800/60 p-4 rounded-2xl flex items-center gap-4 hover:border-slate-700/80 transition"
                    >
                      <img src={item.imageUrl} alt={item.name} className="w-14 h-14 object-cover rounded-xl border border-slate-800 shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-[9px] font-bold text-indigo-400 bg-indigo-950/50 border border-indigo-900/40 px-1.5 py-0.5 rounded">
                            {item.originalName}
                          </span>
                        </div>
                        <h5 className="text-sm font-bold text-slate-200 truncate">{item.name}</h5>
                        <p className="text-[11px] text-slate-400 truncate mt-0.5">{item.description}</p>
                      </div>
                      <div className="text-right shrink-0">
                        <div className="text-xs font-extrabold text-slate-300">₩{item.price?.toLocaleString()}</div>
                        <div className="text-[10px] text-emerald-400 font-bold mt-0.5 font-mono">예상 마진: ₩{item.estimatedMargin?.toLocaleString()}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* 푸터 */}
            <div className="flex items-center justify-end gap-3 px-8 py-5 border-t border-slate-800 bg-slate-950/80">
              <button 
                onClick={() => setSelectedSavedSession(null)}
                className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-bold transition cursor-pointer shadow-md"
              >
                확인 완료
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 확대보기 라이트박스 */}
      {enlargedUrl && (
        <div
          className="fixed inset-0 z-[200] bg-black/80 flex items-center justify-center p-6 cursor-zoom-out animate-in fade-in duration-150"
          onClick={() => setEnlargedUrl(null)}
        >
          <button
            type="button"
            onClick={() => setEnlargedUrl(null)}
            className="absolute top-4 right-4 p-2 bg-white/10 hover:bg-white/20 text-white rounded-full transition cursor-pointer"
            title="닫기"
          >
            <X size={22} />
          </button>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={enlargedUrl}
            alt="확대 이미지"
            className="max-w-[90vw] max-h-[85vh] object-contain rounded-xl shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </div>
  );
}
