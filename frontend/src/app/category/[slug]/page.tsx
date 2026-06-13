"use client";

import { motion } from "framer-motion";
import { API_URL } from "@/lib/api";
import { useParams } from "next/navigation";
import ProductList, { Product } from "@/components/ProductList";
import { useEffect, useState, useRef } from "react";
import { Shirt, Briefcase, Watch, Sparkles, Truck, Loader2, Footprints } from "lucide-react";

// Subcategory mappings per main category
const SUB_CATEGORIES: Record<string, string[]> = {
  "남성의류": ["전체", "아우터", "상의", "하의", "세트"],
  "여성의류": ["전체", "아우터", "상의", "하의", "원피스"],
  "가방": ["전체", "토트백", "크로스백", "백팩", "에코백"],
  "지갑": ["전체", "반지갑", "장지갑", "카드지갑"],
  "시계": ["전체", "메탈시계", "가죽시계", "스마트워치"],
  "악세사리": ["전체", "목걸이", "반지", "귀걸이", "팔찌"],
  "신발": ["전체", "남성신발", "여성신발"],
  "국내배송": ["전체", "의류", "잡화", "기타"],
  "summer-sale": ["전체", "바캉스룩", "수영복/비치", "여름시즌오프"]
};

// 신발의 중분류별 소분류 상세 구성 (슬러그 매핑)
const SHOES_SUB_CATEGORIES: Record<string, { name: string, slug: string }[]> = {
  "남성신발": [
    { name: "전체", slug: "shoes-mens" },
    { name: "스니커즈/운동화", slug: "shoes-mens-sneakers" },
    { name: "로퍼/구두", slug: "shoes-mens-formal" },
    { name: "샌들/슬리퍼", slug: "shoes-mens-sandals" }
  ],
  "여성신발": [
    { name: "전체", slug: "shoes-womens" },
    { name: "스니커즈/운동화", slug: "shoes-womens-sneakers" },
    { name: "플랫/구두", slug: "shoes-womens-formal" },
    { name: "샌들/슬리퍼", slug: "shoes-womens-sandals" }
  ]
};

// Theme configuration per category
const CATEGORY_THEMES: Record<string, any> = {
  "신발": {
    bg: "from-blue-100 via-sky-50 to-white dark:from-blue-950 dark:via-sky-900 dark:to-slate-900",
    text: "text-blue-900 dark:text-blue-100",
    accent: "text-blue-600",
    icon: <Footprints size={48} />,
    desc: "캐주얼 스니커즈부터 고급 포멀 로퍼까지, 완벽한 스타일의 마침표를 찍어줄 신발 컬렉션."
  },
  "의류": {
    bg: "from-indigo-100 via-blue-50 to-white dark:from-indigo-950 dark:via-blue-900 dark:to-slate-900",
    text: "text-indigo-900 dark:text-indigo-100",
    accent: "text-indigo-600",
    icon: <Shirt size={48} />,
    desc: "트렌디한 디자인과 편안한 착용감을 선사하는 프리미엄 의류 컬렉션을 만나보세요."
  },
  "뷰티": {
    bg: "from-rose-100 via-pink-50 to-white dark:from-rose-950 dark:via-pink-900 dark:to-slate-900",
    text: "text-rose-900 dark:text-rose-100",
    accent: "text-rose-500",
    icon: <Sparkles size={48} />,
    desc: "당신의 피부를 빛나게 해줄 스킨케어와 다채로운 메이크업 제품입니다."
  },
  "가방": {
    bg: "from-amber-100 via-orange-50 to-white dark:from-amber-950 dark:via-orange-900 dark:to-slate-900",
    text: "text-amber-900 dark:text-amber-100",
    accent: "text-amber-600",
    icon: <Briefcase size={48} />,
    desc: "일상과 특별한 순간을 함께할 세련된 가방 컬렉션."
  },
  "액세서리": {
    bg: "from-slate-900 via-black to-slate-800",
    text: "text-slate-100",
    accent: "text-amber-500", // Gold accent
    icon: <Watch size={48} />,
    desc: "고급스러운 무드를 완성하는 시계와 주얼리를 확인해보세요."
  },
  "빠른배송": {
    bg: "from-emerald-100 via-teal-50 to-white dark:from-emerald-950 dark:via-teal-900 dark:to-slate-900",
    text: "text-emerald-900 dark:text-emerald-100",
    accent: "text-emerald-600",
    icon: <Truck size={48} />,
    desc: "오후 2시 이전 결제 완료 시 당일 발송. 내일 바로 만나보세요."
  },
  "summer-sale": {
    bg: "from-cyan-100 via-sky-50 to-white dark:from-sky-950 dark:via-blue-900 dark:to-slate-900",
    text: "text-sky-900 dark:text-sky-100",
    accent: "text-sky-500",
    icon: <Sparkles size={48} className="text-cyan-500 animate-pulse" />,
    desc: "최대 50% 역대급 할인! 올여름 바캉스 준비는 여기서 완벽하게 끝내세요."
  }
};

const DEFAULT_THEME = {
  bg: "from-slate-100 to-white dark:from-slate-800 dark:to-slate-900",
  text: "text-slate-800 dark:text-slate-100",
  accent: "text-blue-500",
  icon: <Sparkles size={48} />,
  desc: "AI 비전 기술을 통해 개인에게 가장 잘 어울리는 스타일을 추천합니다."
};

export default function CategoryPage() {
  const params = useParams();
  const rawSlug = params.slug as string;
  const decodeSlug = decodeURIComponent(rawSlug);
  
  const theme = CATEGORY_THEMES[decodeSlug] || DEFAULT_THEME;
  const subCategories = SUB_CATEGORIES[decodeSlug] || ["전체"];
  
  const [activeSub, setActiveSub] = useState("전체");
  const [activeDetailSlug, setActiveDetailSlug] = useState("전체");
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);

  // 브랜드 교차 필터 상태 정의
  const [selectedBrand, setSelectedBrand] = useState("전체");
  const [availableBrands, setAvailableBrands] = useState<{ id: number | null; name: string }[]>([]);

  const isFirstRender = useRef(true);

  // 클라이언트 마운트 시 URL 쿼리 파라미터 파싱 및 필터 세팅
  useEffect(() => {
    if (typeof window !== "undefined") {
      const searchParams = new URLSearchParams(window.location.search);
      const subCategoryParam = searchParams.get("sub_category");
      if (subCategoryParam) {
        if (subCategoryParam.startsWith("shoes-")) {
          if (subCategoryParam.includes("-mens")) {
            setActiveSub("남성신발");
            setActiveDetailSlug(subCategoryParam);
          } else if (subCategoryParam.includes("-womens")) {
            setActiveSub("여성신발");
            setActiveDetailSlug(subCategoryParam);
          } else {
            const midName = subCategoryParam === "shoes-mens" ? "남성신발" : "여성신발";
            setActiveSub(midName);
            setActiveDetailSlug("전체");
          }
        } else {
          setActiveSub(subCategoryParam);
        }
      }
    }
  }, [decodeSlug]);

  // activeSub가 변경될 때 소분류 선택을 "전체"로 리셋 (최초 마운트 랜딩 시에는 초기화 스킵)
  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    setActiveDetailSlug("전체");
  }, [activeSub]);

  useEffect(() => {
    async function fetchCategoryItems() {
      setLoading(true);
      try {
        let subCategoryVal = "";
        if (decodeSlug === "신발" && activeSub !== "전체") {
          if (activeDetailSlug !== "전체") {
            subCategoryVal = activeDetailSlug;
          } else {
            subCategoryVal = activeSub === "남성신발" ? "shoes-mens" : "shoes-womens";
          }
        } else {
          if (activeSub !== "전체") {
            subCategoryVal = activeSub;
          }
        }

        const queryParam = subCategoryVal ? `?sub_category=${encodeURIComponent(subCategoryVal)}` : "";
        const apiUrl = API_URL;
        const res = await fetch(`${apiUrl}/api/products/category/${encodeURIComponent(decodeSlug)}${queryParam}`);
        if (res.ok) {
          setProducts(await res.json());
        }
      } catch (error) {
        console.warn("Fetch error:", error);
      } finally {
        setLoading(false);
      }
    }
    fetchCategoryItems();
  }, [decodeSlug, activeSub, activeDetailSlug]);

  // 해당 카테고리에 할당된 모든 공식 브랜드 가져오기
  const [activeBrandNames, setActiveBrandNames] = useState<Set<string>>(new Set());

  useEffect(() => {
    async function fetchCategoryBrands() {
      try {
        const res = await fetch(`${API_URL}/api/products/brands?category_name=${encodeURIComponent(decodeSlug)}`);
        if (res.ok) {
          const brandData = await res.json();
          // "전체" 필터 칩 추가
          const brandList = [{ id: null, name: "전체" }, ...brandData];
          setAvailableBrands(brandList);
        }
      } catch (error) {
        console.warn("Failed to fetch brands for category page", error);
      }
    }
    if (decodeSlug) {
      fetchCategoryBrands();
    }
  }, [decodeSlug]);

  // 현재 상품 데이터에 존재하는 브랜드 이름 목록 (필터 칩 활성/비활성 제어용)
  useEffect(() => {
    const names = new Set<string>();
    products.forEach((p: any) => {
      if (p.brand_name) {
        names.add(p.brand_name);
      }
    });
    setActiveBrandNames(names);
    setSelectedBrand("전체");
  }, [products]);

  const displayedProducts = (selectedBrand === "전체" || decodeSlug === "국내배송")
    ? products
    : products.filter((p: any) => p.brand_name === selectedBrand);

  return (
    <div className={`min-h-screen bg-gradient-to-br ${theme.bg} transition-colors duration-700`}>
      {/* Category Hero Banner */}
      <div className="pt-32 pb-16 px-8 max-w-7xl mx-auto flex flex-col items-center text-center">
        <motion.div 
          initial={{ scale: 0.8, opacity: 0 }} 
          animate={{ scale: 1, opacity: 1 }}
          className={`mb-6 ${theme.accent}`}
        >
          {theme.icon}
        </motion.div>
        
        <motion.h1 
          initial={{ y: 20, opacity: 0 }} 
          animate={{ y: 0, opacity: 1 }}
          className={`text-5xl md:text-6xl font-extrabold tracking-tight ${theme.text} mb-4 uppercase`}
        >
          {decodeSlug === "summer-sale" ? "SUMMER SALE" : decodeSlug}
        </motion.h1>
        
        <motion.p 
          initial={{ y: 20, opacity: 0 }} 
          animate={{ y: 0, opacity: 1 }} transition={{ delay: 0.1 }}
          className="text-lg md:text-xl font-medium opacity-80 max-w-2xl"
        >
          {theme.desc}
        </motion.p>
      </div>

      {/* Main Product Grid */}
      <div className="max-w-7xl mx-auto px-6 pb-24">
        
        {/* Subcategory UX Filter Chips */}
        <div className="flex flex-col items-center gap-4 mb-8 -mt-6">
          <div className="flex flex-wrap items-center justify-center gap-2">
             {subCategories.map(sub => (
                <button 
                  key={sub}
                  onClick={() => setActiveSub(sub)}
                  className={`px-5 py-2 rounded-full text-sm font-bold border transition-all ${
                    activeSub === sub 
                    ? 'bg-slate-900 border-slate-900 text-white dark:bg-slate-100 dark:border-slate-100 dark:text-slate-900 shadow-md transform scale-105' 
                    : 'bg-white/50 border-white/50 text-slate-600 hover:bg-white dark:bg-slate-800/50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800 backdrop-blur-sm'
                  }`}
                >
                  {sub}
                </button>
             ))}
          </div>

          {/* 3단계 상세 소분류 필터 (신발 카테고리 전용) */}
          {decodeSlug === "신발" && activeSub !== "전체" && SHOES_SUB_CATEGORIES[activeSub] && (
            <motion.div 
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex flex-wrap items-center justify-center gap-2 p-2 bg-slate-100/50 dark:bg-slate-900/30 rounded-2xl border border-slate-200/50 dark:border-slate-800/50 backdrop-blur-sm"
            >
              {SHOES_SUB_CATEGORIES[activeSub].map(subOpt => (
                <button
                  key={subOpt.slug}
                  onClick={() => setActiveDetailSlug(subOpt.slug)}
                  className={`px-4 py-1.5 rounded-xl text-xs font-bold transition-all ${
                    activeDetailSlug === subOpt.slug
                    ? 'bg-blue-600 text-white shadow-sm transform scale-105'
                    : 'text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200'
                  }`}
                >
                  {subOpt.name}
                </button>
              ))}
            </motion.div>
          )}
          {/* 브랜드별 교차 필터 칩 (국내배송 카테고리에서는 브랜드 필터 비활성화) */}
          {decodeSlug !== "국내배송" && availableBrands.length > 2 && (
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex flex-wrap items-center justify-center gap-1.5 p-1.5 bg-slate-100/30 dark:bg-slate-900/10 rounded-xl border border-slate-200/30 dark:border-slate-800/30 backdrop-blur-sm mt-1"
            >
              <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 px-2 select-none">브랜드 필터</span>
              {availableBrands.map(br => {
                const isAll = br.name === "전체";
                const hasProducts = isAll || activeBrandNames.has(br.name);
                
                return (
                  <button
                    key={br.name}
                    onClick={() => {
                      if (!hasProducts) {
                        alert(`현재 '${br.name}' 브랜드의 수입 상품은 해외 배송 또는 통관 준비 중입니다. 신속하게 입고하도록 하겠습니다!`);
                        return;
                      }
                      setSelectedBrand(br.name);
                    }}
                    className={`px-3 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                      selectedBrand === br.name
                        ? 'bg-blue-600 text-white shadow-sm transform scale-105'
                        : hasProducts
                          ? 'text-slate-700 hover:text-slate-900 dark:text-slate-300 dark:hover:text-slate-100 hover:bg-slate-100/50 dark:hover:bg-slate-800/50'
                          : 'text-slate-400 dark:text-slate-600 opacity-40 cursor-not-allowed'
                    }`}
                  >
                    {br.name}
                  </button>
                );
              })}
            </motion.div>
          )}
        </div>

        <div className="glass-panel p-8 rounded-3xl border border-white/20 shadow-2xl bg-white/40 dark:bg-slate-900/40">
           <div className="flex justify-between items-end border-b border-slate-300 dark:border-slate-700 pb-4 mb-8">
              <h2 className="text-2xl font-bold dark:text-white">추천 상품 & 베스트 아이템</h2>
              <span className="text-sm font-semibold text-slate-500">{displayedProducts.length}개의 상품</span>
           </div>
           
           {loading ? (
             <div className="flex flex-col items-center justify-center py-20 text-blue-500">
               <Loader2 size={48} className="animate-spin mb-4" />
               <p className="font-semibold">AI 상품 데이터를 불러오는 중입니다...</p>
             </div>
           ) : displayedProducts.length > 0 ? (
             <ProductList products={displayedProducts} linkToDetail={true} selectedIds={[]} />
           ) : (
             <div className="text-center py-20 text-slate-500">
               <span className="text-4xl mb-4 block">😕</span>
               <p className="text-xl font-semibold mb-2">상품이 존재하지 않습니다.</p>
               <p>해당 카테고리[{decodeSlug} - {activeSub}]에 등록된 상품이 없습니다.</p>
             </div>
           )}
        </div>
      </div>
    </div>
  );
}
