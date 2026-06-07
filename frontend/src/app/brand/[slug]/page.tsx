"use client";

import { motion } from "framer-motion";
import { API_URL } from "@/lib/api";
import { useParams, useRouter } from "next/navigation";
import ProductList, { Product } from "@/components/ProductList";
import { useEffect, useState, useRef } from "react";
import { Sparkles, Loader2, ArrowLeft, ShieldCheck, Heart } from "lucide-react";

// 브랜드별 럭셔리 전용 테마 구성 (Wow Factor: 각 명품 브랜드 고유의 컬러 브랜딩 제공)
const BRAND_THEMES: Record<string, { bg: string; text: string; accent: string; desc: string; bannerTitle: string }> = {
  "chanel": {
    bg: "from-zinc-900 via-stone-950 to-neutral-950",
    text: "text-zinc-100",
    accent: "text-white border-white/40 bg-white/5 hover:bg-white/10",
    bannerTitle: "CHANEL",
    desc: "가장 순수한 럭셔리, 블랙 앤 화이트의 우아함. 샤넬 오트쿠튀르 헤리티지 에디션."
  },
  "louis-vuitton": {
    bg: "from-amber-950 via-stone-900 to-black",
    text: "text-amber-100/90",
    accent: "text-amber-500 border-amber-500/30 bg-amber-500/5 hover:bg-amber-500/10",
    bannerTitle: "LOUIS VUITTON",
    desc: "클래식 모노그램의 깊은 아우라. 한계를 뛰어넘는 최고급 럭셔리 패션 트래블 컬렉션."
  },
  "gucci": {
    bg: "from-stone-900 via-emerald-950 to-zinc-950",
    text: "text-emerald-100",
    accent: "text-emerald-400 border-emerald-500/30 bg-emerald-500/5 hover:bg-emerald-500/10",
    bannerTitle: "GUCCI",
    desc: "이탈리아 감성의 현대적 맥시멀리즘. 대담하고 매혹적인 디자인으로 연출하는 구찌 하우스."
  },
  "prada": {
    bg: "from-neutral-900 via-stone-950 to-black",
    text: "text-neutral-200",
    accent: "text-stone-300 border-stone-800 bg-stone-900/50 hover:bg-stone-800/80",
    bannerTitle: "PRADA",
    desc: "지적인 미니멀리즘과 실용적 우아함의 정수. 밀라노 쿠튀르 시그니처 삼각 로고 에디션."
  },
  "hermes": {
    bg: "from-orange-950 via-zinc-900 to-black",
    text: "text-orange-100",
    accent: "text-orange-500 border-orange-500/30 bg-orange-500/5 hover:bg-orange-500/10",
    bannerTitle: "HERMÈS",
    desc: "타협 없는 전통 장인 정신. 주황빛 실크와 최고급 하이엔드 하드웨어 가죽의 정점."
  },
  "dior": {
    bg: "from-slate-900 via-slate-950 to-zinc-950",
    text: "text-slate-100",
    accent: "text-slate-350 border-slate-800 bg-slate-800/30 hover:bg-slate-800/60",
    bannerTitle: "DIOR",
    desc: "파리지앵의 로망과 궁극의 정제된 페미닌/머스큘린 실루엣. 오트쿠튀르의 상징 디올 컬렉션."
  },
  "bottega-veneta": {
    bg: "from-green-950 via-stone-900 to-neutral-950",
    text: "text-green-100",
    accent: "text-green-400 border-green-500/20 bg-green-500/5 hover:bg-green-500/10",
    bannerTitle: "BOTTEGA VENETA",
    desc: "인트레치아토 위빙 가죽 기법의 완결판. 로고 없는 럭셔리, 보테가베네타 하우스 에디션."
  },
  "miu-miu": {
    bg: "from-rose-950 via-slate-900 to-black",
    text: "text-rose-100",
    accent: "text-rose-450 border-rose-500/20 bg-rose-500/5 hover:bg-rose-500/10",
    bannerTitle: "MIU MIU",
    desc: "사랑스럽고 실험적인 Y2K 럭셔리 실루엣. 젊고 감각적인 미우미우 크리에이션 컬렉션."
  }
};

const DEFAULT_THEME = {
  bg: "from-slate-900 via-slate-950 to-black",
  text: "text-slate-200",
  accent: "text-blue-500 border-slate-800 bg-slate-900/50 hover:bg-slate-800",
  bannerTitle: "LUXURY BRAND",
  desc: "밀라노와 파리 패션위크를 수놓은 글로벌 탑티어 하이엔드 디자이너 브랜드 컬렉션."
};

export default function BrandPage() {
  const params = useParams();
  const router = useRouter();
  const rawSlug = params.slug as string;
  const slug = rawSlug ? rawSlug.toLowerCase() : "";

  // 브랜드 텍스트 및 스타일 테마 매핑
  const theme = BRAND_THEMES[slug] || DEFAULT_THEME;

  const [allProducts, setAllProducts] = useState<Product[]>([]);
  const [filteredProducts, setFilteredProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<string[]>(["전체"]);
  const [activeCategory, setActiveCategory] = useState("전체");
  const [loading, setLoading] = useState(true);
  const [brandInfo, setBrandInfo] = useState<{ name: string; eng_name: string } | null>(null);

  // 1. 브랜드의 상품 로드 및 카테고리 수집
  useEffect(() => {
    async function fetchBrandProducts() {
      setLoading(true);
      try {
        const res = await fetch(`${API_URL}/api/products?brand_slug=${slug}`);
        if (res.ok) {
          const data = (await res.json()) as Product[];
          setAllProducts(data);
          setFilteredProducts(data);

          // 상품 목록에서 실시간으로 카테고리 목록을 수집 (교차 필터링)
          const uniqueCats = new Set<string>();
          data.forEach((p: any) => {
            if (p.category_name) {
              uniqueCats.add(p.category_name);
            }
          });
          setCategories(["전체", ...Array.from(uniqueCats)]);

          // 첫 상품 정보에서 브랜드 한글/영문명 세팅
          if (data.length > 0) {
            const first = data[0] as any;
            if (first.brand_name) {
              setBrandInfo({
                name: first.brand_name,
                eng_name: first.brand_eng_name || first.brand_name
              });
            }
          }
        }
      } catch (error) {
        console.warn("Brand fetch error:", error);
      } finally {
        setLoading(false);
      }
    }
    
    if (slug) {
      fetchBrandProducts();
    }
  }, [slug]);

  // 만약 상품 목록이 비어 있는 경우 백엔드 브랜드 정보 보충용 호출
  useEffect(() => {
    if (!brandInfo && slug) {
      async function fetchBrandInfo() {
        try {
          const res = await fetch(`${API_URL}/api/products/brands`);
          if (res.ok) {
            const brands = await res.json();
            const found = brands.find((b: any) => b.slug === slug);
            if (found) {
              setBrandInfo({ name: found.name, eng_name: found.eng_name });
            }
          }
        } catch (e) {
          console.warn(e);
        }
      }
      fetchBrandInfo();
    }
  }, [slug, brandInfo]);

  // 2. 카테고리 칩 선택 시 실시간 필터링
  useEffect(() => {
    if (activeCategory === "전체") {
      setFilteredProducts(allProducts);
    } else {
      setFilteredProducts(
        allProducts.filter((p: any) => p.category_name === activeCategory)
      );
    }
  }, [activeCategory, allProducts]);

  return (
    <div className={`min-h-screen bg-gradient-to-br ${theme.bg} text-white transition-all duration-700 pb-24`}>
      
      {/* 럭셔리 네비게이션 복귀 바 */}
      <div className="pt-28 px-6 max-w-7xl mx-auto flex items-center justify-between">
        <button
          onClick={() => router.push("/")}
          className="flex items-center gap-2 px-4 py-2 rounded-full border border-white/10 bg-white/5 hover:bg-white/10 transition text-sm font-bold cursor-pointer text-slate-300 hover:text-white"
        >
          <ArrowLeft size={16} />
          <span>쇼핑몰 홈</span>
        </button>
        <div className="flex items-center gap-2 text-xs font-semibold text-slate-400">
          <ShieldCheck size={14} className="text-amber-500" />
          <span>100% 공식 정품 보증 & 해외 직배송</span>
        </div>
      </div>

      {/* Brand Hero Banner */}
      <div className="pt-12 pb-16 px-8 max-w-7xl mx-auto flex flex-col items-center text-center">
        <motion.h1
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          className="text-6xl md:text-7xl font-extrabold tracking-tighter mb-4 font-mono select-none"
        >
          {brandInfo?.eng_name.toUpperCase() || theme.bannerTitle}
        </motion.h1>
        
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 0.8 }}
          transition={{ delay: 0.2 }}
          className="h-px w-24 bg-white/20 mb-6"
        />

        <motion.h2
          initial={{ y: 15, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          className="text-xl md:text-2xl font-bold tracking-tight text-slate-300 mb-4"
        >
          {brandInfo?.name || theme.bannerTitle} 공식 수입관
        </motion.h2>

        <motion.p
          initial={{ y: 15, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.1 }}
          className="text-sm md:text-base text-slate-400 font-medium max-w-2xl leading-relaxed"
        >
          {theme.desc}
        </motion.p>
      </div>

      {/* Main Container */}
      <div className="max-w-7xl mx-auto px-6">
        
        {/* 교차 품목 카테고리 필터 (기획안의 듀얼 필터 구현) */}
        {categories.length > 1 && (
          <div className="flex flex-col items-center gap-3 mb-12">
            <span className="text-xs font-bold tracking-wider text-slate-500 uppercase">품목별로 카테고리 분류</span>
            <div className="flex flex-wrap items-center justify-center gap-2">
              {categories.map((cat) => (
                <button
                  key={cat}
                  onClick={() => setActiveCategory(cat)}
                  className={`px-5 py-2.5 rounded-full text-xs font-bold border transition-all cursor-pointer ${
                    activeCategory === cat
                      ? "bg-white text-black border-white shadow-lg transform scale-105"
                      : "bg-white/5 border-white/10 text-slate-400 hover:text-white hover:bg-white/10"
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Product Grid Area */}
        <div className="bg-white/5 dark:bg-slate-950/20 backdrop-blur-md p-8 rounded-3xl border border-white/10 shadow-2xl">
          <div className="flex justify-between items-end border-b border-white/10 pb-4 mb-8">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              <h3 className="text-xl font-bold tracking-tight text-slate-200">
                {brandInfo?.name || "브랜드"} 오리지널 정품 컬렉션
              </h3>
            </div>
            <span className="text-xs font-semibold text-slate-450">
              총 {filteredProducts.length}개의 수집 상품
            </span>
          </div>

          {loading ? (
            <div className="flex flex-col items-center justify-center py-24 text-slate-350">
              <Loader2 size={48} className="animate-spin text-white/50 mb-4" />
              <p className="font-semibold text-sm">LUXAI 정품 공급망 데이터를 불러오는 중...</p>
            </div>
          ) : filteredProducts.length > 0 ? (
            <div className="dark">
              <ProductList products={filteredProducts} linkToDetail={true} selectedIds={[]} />
            </div>
          ) : (
            <div className="text-center py-24 text-slate-500">
              <span className="text-5xl mb-4 block">👜</span>
              <p className="text-lg font-bold mb-2">공급망 준비 중</p>
              <p className="text-sm">
                현재 [{brandInfo?.name || "해당 브랜드"}] 카테고리에 리스팅된 상품이 아직 승인 보류 중입니다.
              </p>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
