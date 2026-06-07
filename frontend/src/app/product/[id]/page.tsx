"use client";

import { useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import { useParams, useRouter } from "next/navigation";
import { motion } from "framer-motion";
import Link from "next/link";
import { useAuth } from "@/hooks/useAuth";
import DOMPurify from "isomorphic-dompurify";
import {
  ArrowLeft,
  ShoppingBag,
  Heart,
  Share2,
  Truck,
  Shield,
  RefreshCw,
  Minus,
  Plus,
  Tag,
  Star,
  Sparkles,
  ChevronRight,
  Loader2,
  AlertCircle,
} from "lucide-react";
import ImageGallery from "@/components/ImageGallery";
import PremiumVtonModal from "@/components/PremiumVtonModal";
import CheckoutModal from "@/components/CheckoutModal";
import SmartFittingCanvas from "@/components/SmartFittingCanvas";
import InlineProductEditor from "@/components/InlineProductEditor";

interface ProductDetail {
  id: number;
  name: string;
  cn_name?: string;
  category: string;
  category_id: number;
  description?: string;
  description_html?: string;
  base_price: number;
  sale_price?: number;
  discount_rate?: number;
  stock_quantity: number;
  sku?: string;
  keywords: string[];
  images: string[];
  ai_fitting_image_url?: string;
  transparent_item_image_url?: string;
  video_url?: string;
  created_at?: string;
  related_products: RelatedProduct[];
}

interface RelatedProduct {
  id: number;
  name: string;
  price: number;
  sale_price?: number;
  discount_rate?: number;
  image: string;
}

export default function ProductDetailPage() {
  const params = useParams();
  const router = useRouter();
  const productId = params.id as string;
  const { user } = useAuth();

  const [product, setProduct] = useState<ProductDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [errors, setError] = useState<string | null>(null);
  const [quantity, setQuantity] = useState(1);
  const [isWished, setIsWished] = useState(false);
  const [isVtonOpen, setIsVtonOpen] = useState(false);
  const [isCheckoutOpen, setIsCheckoutOpen] = useState(false);
  const [addedToCart, setAddedToCart] = useState(false);
  const [showFitting, setShowFitting] = useState(false);
  const [reviews, setReviews] = useState<{ count: number; average: number; items: any[] }>({ count: 0, average: 0, items: [] });

  // 미승인 회원(5등급) 및 비로그인 게스트 마스킹 처리 룰
  const isMasked = user === null || user.grade === 5;

  useEffect(() => {
    async function fetchProduct() {
      setLoading(true);
      setError(null);
      try {
        const apiUrl = API_URL;
        const res = await fetch(
          `${apiUrl}/api/products/${productId}`
        );
        if (!res.ok) {
          if (res.status === 404) setError("해당 상품을 찾을 수 없습니다.");
          else setError("상품 데이터를 불러오는 데 실패했습니다.");
          return;
        }
        const data = await res.json();
        setProduct(data);
      } catch {
        setError("서버에 연결할 수 없습니다. 잠시 후 다시 시도해주세요.");
      } finally {
        setLoading(false);
      }
    }
    if (productId) fetchProduct();
  }, [productId]);

  // E1: 상품 후기 조회 (공개 — 비로그인도 볼 수 있음)
  useEffect(() => {
    if (!productId) return;
    fetch(`${API_URL}/api/reviews/product/${productId}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (d) setReviews(d); })
      .catch(() => {});
  }, [productId]);

  // 장바구니 담기
  const handleAddToCart = async () => {
    if (isMasked) {
      alert("회원 승인이 필요한 기능입니다. (미가입 및 비로그인 상태는 가격 확인 및 구매가 불가능합니다.)");
      if (!user) router.push("/login");
      return;
    }

    const token = localStorage.getItem("token");
    if (!token) {
      alert("로그인이 필요합니다.");
      router.push("/login");
      return;
    }

    try {
      const apiUrl = API_URL;
      const res = await fetch(`${apiUrl}/api/cart/items`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          product_id: parseInt(productId),
          quantity,
        }),
      });
      if (res.ok) {
        setAddedToCart(true);
        setTimeout(() => setAddedToCart(false), 2000);
      } else {
        // H3: 서버 메시지(재고 부족 등) 그대로 표시
        const err = await res.json().catch(() => ({}));
        alert(err.detail || "장바구니 담기에 실패했습니다.");
      }
    } catch (err) {
      console.error(err);
    }
  };

  // 위시리스트 토글
  const toggleWishlist = async () => {
    if (isMasked) {
      alert("회원 승인이 필요한 기능입니다. (미가입 및 비로그인 상태는 사용이 불가능합니다.)");
      if (!user) router.push("/login");
      return;
    }

    const token = localStorage.getItem("token");
    if (!token) {
      alert("로그인이 필요합니다.");
      router.push("/login");
      return;
    }

    try {
      const apiUrl = API_URL;
      const res = await fetch(`${apiUrl}/api/wishlist/toggle`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ product_id: parseInt(productId) }),
      });
      if (res.ok) {
        const data = await res.json();
        setIsWished(data.status === "added");
      }
    } catch (err) {
      console.error(err);
    }
  };

  // 공유
  const handleShare = async () => {
    if (navigator.share) {
      await navigator.share({
        title: product?.name,
        url: window.location.href,
      });
    } else {
      await navigator.clipboard.writeText(window.location.href);
      alert("링크가 복사되었습니다!");
    }
  };

  // --- 로딩 상태 ---
  if (loading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-br from-slate-50 to-white dark:from-slate-900 dark:to-slate-800">
        <Loader2 size={48} className="animate-spin text-blue-500 mb-4" />
        <p className="text-slate-500 font-medium">상품 데이터 불러오는 중...</p>
      </div>
    );
  }

  // --- 에러 상태 ---
  if (errors || !product) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-br from-slate-50 to-white dark:from-slate-900 dark:to-slate-800">
        <span className="text-6xl mb-4">😕</span>
        <h2 className="text-2xl font-bold text-slate-800 dark:text-white mb-2">
          {errors || "상품 데이터를 불러올 수 없습니다."}
        </h2>
        <button
          onClick={() => router.back()}
          className="mt-4 px-6 py-3 bg-blue-600 text-white rounded-xl font-semibold hover:bg-blue-700 transition"
        >
          뒤로 가기
        </button>
      </div>
    );
  }

  const finalPrice = product.sale_price || product.base_price;
  const hasDiscount =
    product.sale_price &&
    product.sale_price < product.base_price;
  const inStock = product.stock_quantity > 0;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50/30 dark:from-slate-900 dark:via-slate-800 dark:to-slate-900">
      {/* Breadcrumb */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <nav className="flex items-center gap-2 text-sm text-slate-500">
          <Link href="/" className="hover:text-blue-600 transition">
            홈
          </Link>
          <ChevronRight size={14} />
          <Link
            href={`/category/${encodeURIComponent(product.category)}`}
            className="hover:text-blue-600 transition"
          >
            {product.category}
          </Link>
          <ChevronRight size={14} />
          <span className="text-slate-800 dark:text-white font-medium truncate max-w-[200px]">
            {product.name}
          </span>
        </nav>
      </div>

      {/* 메인 2컬럼 레이아웃 */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-16">
        {/* 미가입 회원 경고 메시지 상단 배치 */}
        {isMasked && (
          <div className="mb-6 bg-slate-900 border border-slate-800 text-slate-300 p-4 rounded-2xl flex items-center space-x-3 shadow-xl">
            <AlertCircle className="text-amber-500 animate-pulse flex-shrink-0" size={24} />
            <div className="text-sm">
              <span className="font-bold text-white">🔒 회원 전용 안내 :</span> 본 사이트는 대리점 및 회원 전용 폐쇄몰로 운영됩니다. 로그인 후 관리자의 승인을 거쳐야 가격 조회 및 실결제, 스마트 피팅 사용 권한이 활성화됩니다.
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 lg:gap-12">
          {/* 좌측: 이미지 갤러리 */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            className="sticky top-24 self-start"
          >
            <ImageGallery
              images={product.images}
              productName={product.name}
              videoUrl={product.video_url || undefined}
            />
          </motion.div>

          {/* 우측: 상품 정보 및 구매 */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.1 }}
            className="flex flex-col gap-6"
          >
            {/* 카테고리 & SKU */}
            <div className="flex items-center gap-3">
              <span className="px-3 py-1 bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 text-xs font-bold rounded-full">
                {product.category}
              </span>
              {product.sku && (
                <span className="text-xs text-slate-400 font-mono">
                  SKU: {product.sku}
                </span>
              )}
            </div>

            {/* 상품명 */}
            <InlineProductEditor
              productId={product.id}
              fieldName="kr_name"
              initialValue={product.name}
              className="text-2xl md:text-3xl lg:text-4xl font-extrabold text-slate-900 dark:text-white leading-tight tracking-tight block"
              onSuccess={(newVal) => setProduct(prev => prev ? { ...prev, name: newVal } : null)}
            >
              {product.name}
            </InlineProductEditor>

            {/* 가격 */}
            <div className="flex items-end gap-4">
              {isMasked ? (
                <div className="bg-slate-100 dark:bg-slate-800/80 px-4 py-3 rounded-2xl border border-slate-200/50 dark:border-slate-700/50 flex items-center">
                  <span className="text-lg font-bold text-slate-500 dark:text-slate-400 flex items-center">
                    <span className="mr-2">🔒</span> 회원전용 (가입 승인 대기)
                  </span>
                </div>
              ) : (
                <>
                  <div className="flex items-baseline gap-3">
                    <InlineProductEditor
                      productId={product.id}
                      fieldName={product.sale_price ? "sale_price" : "base_price"}
                      initialValue={product.sale_price || product.base_price}
                      className="text-3xl md:text-4xl font-black text-slate-900 dark:text-white animate-in fade-in"
                      onSuccess={(newVal) => setProduct(prev => {
                        if (!prev) return null;
                        if (prev.sale_price !== undefined && prev.sale_price !== null) {
                          return { ...prev, sale_price: newVal };
                        } else {
                          return { ...prev, base_price: newVal };
                        }
                      })}
                    >
                      {finalPrice.toLocaleString()}원
                    </InlineProductEditor>
                    {hasDiscount && (
                      <span className="text-lg text-slate-400 line-through">
                        {product.base_price.toLocaleString()}원
                      </span>
                    )}
                  </div>
                  {hasDiscount && product.discount_rate && (
                    <span className="px-3 py-1.5 bg-gradient-to-r from-red-500 to-rose-500 text-white text-sm font-extrabold rounded-lg shadow-md shadow-red-500/30 animate-pulse">
                      {product.discount_rate}% OFF
                    </span>
                  )}
                </>
              )}
            </div>

            {/* 요약 설명 */}
            <hr className="border-slate-200 dark:border-slate-700" />

            {product.description && (
              <p className="text-slate-600 dark:text-slate-300 leading-relaxed text-base">
                {product.description}
              </p>
            )}

            {/* 키워드 태그 */}
            {product.keywords.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {product.keywords.map((kw, i) => (
                  <span
                    key={i}
                    className="inline-flex items-center gap-1 px-3 py-1.5 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 text-xs font-medium rounded-full border border-slate-200 dark:border-slate-700"
                  >
                    <Tag size={12} />
                    {kw}
                  </span>
                ))}
              </div>
            )}

            {/* 재고 & 배송 정보 */}
            <div className="flex items-center gap-2">
              <div
                className={`w-2.5 h-2.5 rounded-full ${inStock ? "bg-emerald-500 animate-pulse" : "bg-red-500"}`}
              />
              <span
                className={`text-sm font-semibold ${inStock ? "text-emerald-600 dark:text-emerald-400" : "text-red-500"}`}
              >
                {inStock
                  ? `재고 ${product.stock_quantity > 0 ? "있음" : ""}`
                  : "품절"}
              </span>
            </div>

            {/* 서비스 배지 */}
            <div className="grid grid-cols-3 gap-3 pt-2">
              {[
                {
                  icon: <Truck size={20} />,
                  title: "무료배송",
                  desc: "50,000원 이상",
                },
                {
                  icon: <Shield size={20} />,
                  title: "100% 정품",
                  desc: "정품 보증서",
                },
                {
                  icon: <RefreshCw size={20} />,
                  title: "7일 교환",
                  desc: "무료 반품",
                },
              ].map((item, i) => (
                <div
                  key={i}
                  className="flex flex-col items-center text-center p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-700"
                >
                  <div className="text-blue-500 mb-1">{item.icon}</div>
                  <span className="text-xs font-bold text-slate-800 dark:text-white">
                    {item.title}
                  </span>
                  <span className="text-[10px] text-slate-500 mt-0.5">
                    {item.desc}
                  </span>
                </div>
              ))}
            </div>

            {/* 수량 선택 */}
            <div className="flex items-center gap-4 pt-2">
              <span className="text-sm font-semibold text-slate-700 dark:text-white">
                수량
              </span>
              <div className="flex items-center border border-slate-300 dark:border-slate-600 rounded-xl overflow-hidden">
                <button
                  onClick={() => setQuantity((q) => Math.max(1, q - 1))}
                  disabled={!inStock}
                  className="w-10 h-10 flex items-center justify-center hover:bg-slate-100 dark:hover:bg-slate-700 transition"
                >
                  <Minus size={16} />
                </button>
                <span className="w-12 text-center font-bold text-slate-900 dark:text-white">
                  {quantity}
                </span>
                <button
                  onClick={() =>
                    setQuantity((q) =>
                      Math.min(product.stock_quantity, q + 1)
                    )
                  }
                  disabled={!inStock}
                  className="w-10 h-10 flex items-center justify-center hover:bg-slate-100 dark:hover:bg-slate-700 transition"
                >
                  <Plus size={16} />
                </button>
              </div>
              <span className="text-sm text-slate-500">
                합계:{" "}
                <strong className="text-slate-900 dark:text-white">
                  {isMasked ? "회원전용" : `${(finalPrice * quantity).toLocaleString()}원`}
                </strong>
              </span>
            </div>

            {/* CTA 버튼들 */}
            <div className="flex flex-col gap-3 pt-4">
              <div className="flex gap-3">
                {/* 장바구니 */}
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={handleAddToCart}
                  disabled={!inStock}
                  className={`flex-[2] py-4 rounded-2xl font-bold text-lg flex items-center justify-center gap-2 border-2 transition-all ${
                    addedToCart
                      ? "bg-emerald-500 border-emerald-500 text-white"
                      : "border-slate-900 dark:border-white text-slate-900 dark:text-white hover:bg-slate-50 dark:hover:bg-slate-800"
                  } disabled:opacity-30 disabled:grayscale`}
                >
                  <ShoppingBag size={22} />
                  {addedToCart ? "담기 완료! ✓" : "장바구니 담기"}
                </motion.button>

                {/* 바로구매 */}
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => {
                    if (isMasked) {
                      alert("회원 승인이 필요한 기능입니다. (미가입 및 비로그인 상태는 사용이 불가능합니다.)");
                      if (!user) router.push("/login");
                      return;
                    }
                    const token = localStorage.getItem("token");
                    if (!token) {
                      alert("로그인이 필요합니다.");
                      router.push("/login");
                      return;
                    }
                    setIsCheckoutOpen(true);
                  }}
                  disabled={!inStock}
                  className="flex-[2] py-4 bg-blue-600 hover:bg-blue-700 text-white rounded-2xl font-bold text-lg flex items-center justify-center gap-2 shadow-xl shadow-blue-500/30 transition-all disabled:opacity-50"
                >
                  바로 구매하기
                </motion.button>
              </div>

              {/* AI 가상피팅 + 위시리스트 + 공유 */}
              <div className="flex gap-3">
                {/* AI 가상피팅 (핵심 기능) */}
                {product.transparent_item_image_url && (
                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => {
                      if (isMasked) {
                        alert("회원 승인이 필요한 기능입니다. (미가입 및 비로그인 상태는 사용이 불가능합니다.)");
                        if (!user) router.push("/login");
                        return;
                      }
                      setShowFitting(!showFitting);
                    }}
                    className="w-full py-4 rounded-2xl font-bold text-lg bg-gradient-to-r from-violet-600 to-blue-600 text-white flex items-center justify-center gap-3 shadow-xl shadow-violet-500/30 transition-all"
                  >
                    <Sparkles size={22} />
                    🎯 AI 스마트 피팅
                  </motion.button>
                )}

                {/* 위시리스트 */}
                <motion.button
                  whileTap={{ scale: 0.95 }}
                  onClick={toggleWishlist}
                  className={`flex-1 py-4 rounded-2xl font-semibold flex items-center justify-center gap-2 border-2 transition-all ${
                    isWished
                      ? "border-rose-500 bg-rose-50 dark:bg-rose-900/20 text-rose-500"
                      : "border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:border-rose-300"
                  }`}
                >
                  <Heart
                    size={18}
                    fill={isWished ? "currentColor" : "none"}
                  />
                  {isWished ? "찜함" : "찜하기"}
                </motion.button>

                {/* 공유 */}
                <motion.button
                  whileTap={{ scale: 0.95 }}
                  onClick={handleShare}
                  className="flex-1 py-4 rounded-2xl font-semibold flex items-center justify-center gap-2 border-2 border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:border-blue-300 transition-all"
                >
                  <Share2 size={18} />
                  공유
                </motion.button>
              </div>
            </div>

            {/* ========================================= */}
            {/* AI 스마트 피팅 캔버스 (토글) */}
            {/* ========================================= */}
            {showFitting && !isMasked && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.5, ease: "easeInOut" }}
              >
                <SmartFittingCanvas
                  productId={product.id}
                  productName={product.name}
                  transparentImageUrl={
                    product.transparent_item_image_url ||
                    product.ai_fitting_image_url ||
                    product.images[0]
                  }
                  onFittingComplete={(url) => {
                    console.log("Fitting complete:", url);
                  }}
                  onAddToCart={handleAddToCart}
                />
              </motion.div>
            )}

            {/* 상품 상세 설명 (Rich HTML) + 이미지 자동 나열 */}
            <motion.section
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="mt-16"
            >
              <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-6 flex items-center gap-2">
                <Star size={22} className="text-amber-500" />
                상품 상세 정보
              </h2>
              <div className="glass-panel rounded-3xl border border-white/40 shadow-xl p-8 lg:p-12 space-y-8">
                {product.description_html ? (
                  <div
                    className="prose prose-slate dark:prose-invert max-w-none
                      prose-img:rounded-xl prose-img:shadow-lg
                      prose-headings:font-bold prose-a:text-blue-600"
                    dangerouslySetInnerHTML={{
                      __html: DOMPurify.sanitize(product.description_html),
                    }}
                  />
                ) : (
                  <p className="text-slate-600 dark:text-slate-300 leading-relaxed text-base whitespace-pre-wrap">
                    {product.description}
                  </p>
                )}

                {/* 등록된 상품 이미지 자동 나열 */}
                {product.images && product.images.length > 0 && (
                  <div className="flex flex-col items-center gap-6 pt-6 border-t border-slate-100 dark:border-slate-800">
                    <p className="text-xs font-bold text-slate-400 uppercase tracking-widest self-start mb-2">상세 이미지</p>
                    {product.images.map((imgUrl, i) => (
                      <div key={i} className="w-full max-w-3xl rounded-2xl overflow-hidden shadow-md border border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900/40 p-2">
                        <img
                          src={imgUrl}
                          alt={`${product.name} 상세 이미지 ${i + 1}`}
                          className="w-full h-auto object-contain rounded-xl"
                          loading="lazy"
                        />
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </motion.section>

            {/* 상품 후기 (E1) */}
            <motion.section
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="mt-16"
            >
              <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-6 flex items-center gap-2">
                <Star size={22} className="text-amber-500" />
                상품 후기
                {reviews.count > 0 && (
                  <span className="text-base font-semibold text-slate-500">
                    ⭐ {reviews.average} · {reviews.count}개
                  </span>
                )}
              </h2>
              {reviews.items.length === 0 ? (
                <div className="glass-panel rounded-3xl border border-white/40 shadow p-8 text-center text-slate-500">
                  아직 등록된 후기가 없습니다.
                </div>
              ) : (
                <div className="space-y-4">
                  {reviews.items.map((rv) => (
                    <div key={rv.id} className="glass-panel rounded-2xl border border-white/40 shadow p-5">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-slate-800 dark:text-white">{rv.user_name}</span>
                          <span className="text-amber-500 text-sm">
                            {"★".repeat(rv.rating)}{"☆".repeat(5 - rv.rating)}
                          </span>
                        </div>
                        <span className="text-xs text-slate-400">{rv.created_at?.slice(0, 10)}</span>
                      </div>
                      {rv.content && (
                        <p className="text-sm text-slate-600 dark:text-slate-300 whitespace-pre-wrap leading-relaxed">
                          {rv.content}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </motion.section>

            {/* 관련 상품 */}
            {product.related_products.length > 0 && (
              <motion.section
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4 }}
                className="mt-16"
              >
                <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-6">
                  🛍️ 함께 보면 좋은 상품
                </h2>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
                  {product.related_products.map((rp) => (
                    <Link key={rp.id} href={`/product/${rp.id}`}>
                      <motion.div
                        whileHover={{
                          y: -6,
                          boxShadow: "0 12px 40px rgba(0,0,0,0.12)",
                        }}
                        className="glass-panel rounded-2xl overflow-hidden border border-white/30 shadow-md cursor-pointer group"
                      >
                        <div className="aspect-[4/5] bg-white dark:bg-slate-800 flex items-center justify-center overflow-hidden">
                          <img
                            src={rp.image}
                            alt={rp.name}
                            className="w-3/4 object-contain group-hover:scale-105 transition-transform duration-300"
                          />
                        </div>
                        <div className="p-4">
                          <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-200 line-clamp-2 mb-2 leading-snug">
                            {rp.name}
                          </h3>
                          <div className="flex items-baseline gap-2">
                            {isMasked ? (
                              <span className="text-xs font-semibold text-slate-400">
                                🔒 회원전용
                              </span>
                            ) : (
                              <>
                                <span className="text-base font-bold text-slate-900 dark:text-white">
                                  {(rp.sale_price || rp.price).toLocaleString()}원
                                </span>
                                {rp.discount_rate && (
                                  <span className="text-xs font-bold text-red-500">
                                    {rp.discount_rate}%
                                  </span>
                                )}
                              </>
                            )}
                          </div>
                        </div>
                      </motion.div>
                    </Link>
                  ))}
                </div>
              </motion.section>
            )}
          </motion.div>
        </div>
      </div>

      {/* VTON 모달 */}
      <PremiumVtonModal
        isOpen={isVtonOpen && !isMasked}
        onClose={() => setIsVtonOpen(false)}
        onComplete={() => {
          setIsVtonOpen(false);
          router.push("/mypage/ai-studio");
        }}
        product_image_url={
          product.transparent_item_image_url ||
          product.ai_fitting_image_url ||
          product.images[0]
        }
      />

      {/* Checkout 모달 */}
      {isCheckoutOpen && !isMasked && (
        <CheckoutModal
          isOpen={isCheckoutOpen}
          onClose={() => setIsCheckoutOpen(false)}
          product={product}
          quantity={quantity}
          totalAmount={finalPrice * quantity}
          onComplete={(orderNumber) => {
            setIsCheckoutOpen(false);
            router.push("/mypage/orders");
          }}
        />
      )}
    </div>
  );
}