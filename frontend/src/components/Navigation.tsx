"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ShoppingBag, Search, Menu, X, User, LogOut, Settings, MessageSquare } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { usePathname, useRouter } from "next/navigation";
import { useTheme } from "@/components/ThemeProvider";
import { API_URL } from "@/lib/api";

const CATEGORIES = [
  "남성의류", "여성의류", "가방/지갑", "시계/악세사리", "신발", "국내배송"
];

const CATEGORY_MAP: Record<string, string> = {
  "남성의류": "/category/남성의류",
  "여성의류": "/category/여성의류",
  "가방/지갑": "/category/가방",
  "시계/악세사리": "/category/시계",
  "신발": "/category/신발",
  "국내배송": "/category/국내배송"
};

const NAV_SUB_CATEGORIES: Record<string, { name: string; href: string; children?: { name: string; href: string }[] }[]> = {
  "남성의류": [
    { name: "아우터", href: "/category/남성의류?sub_category=아우터" },
    { name: "상의", href: "/category/남성의류?sub_category=상의" },
    { name: "하의", href: "/category/남성의류?sub_category=하의" },
    { name: "세트", href: "/category/남성의류?sub_category=세트" }
  ],
  "여성의류": [
    { name: "아우터", href: "/category/여성의류?sub_category=아우터" },
    { name: "상의", href: "/category/여성의류?sub_category=상의" },
    { name: "하의", href: "/category/여성의류?sub_category=하의" },
    { name: "원피스", href: "/category/여성의류?sub_category=원피스" }
  ],
  "신발": [
    {
      name: "남성신발",
      href: "/category/신발?sub_category=남성신발",
      children: [
        { name: "스니커즈/운동화", href: "/category/신발?sub_category=shoes-mens-sneakers" },
        { name: "로퍼/구두", href: "/category/신발?sub_category=shoes-mens-formal" },
        { name: "샌들/슬리퍼", href: "/category/신발?sub_category=shoes-mens-sandals" }
      ]
    },
    {
      name: "여성신발",
      href: "/category/신발?sub_category=여성신발",
      children: [
        { name: "스니커즈/운동화", href: "/category/신발?sub_category=shoes-womens-sneakers" },
        { name: "플랫/구두", href: "/category/신발?sub_category=shoes-womens-formal" },
        { name: "샌들/슬리퍼", href: "/category/신발?sub_category=shoes-womens-sandals" }
      ]
    }
  ],
  "가방/지갑": [
    {
      name: "가방",
      href: "/category/가방",
      children: [
        { name: "토트백", href: "/category/가방?sub_category=토트백" },
        { name: "크로스백", href: "/category/가방?sub_category=크로스백" },
        { name: "백팩", href: "/category/가방?sub_category=백팩" }
      ]
    },
    {
      name: "지갑",
      href: "/category/지갑",
      children: [
        { name: "반지갑", href: "/category/지갑?sub_category=반지갑" },
        { name: "장지갑", href: "/category/지갑?sub_category=장지갑" }
      ]
    }
  ],
  "시계/악세사리": [
    {
      name: "시계",
      href: "/category/시계",
      children: [
        { name: "메탈시계", href: "/category/시계?sub_category=메탈시계" },
        { name: "가죽시계", href: "/category/시계?sub_category=가죽시계" }
      ]
    },
    {
      name: "악세사리",
      href: "/category/악세사리",
      children: [
        { name: "목걸이", href: "/category/악세사리?sub_category=목걸이" },
        { name: "반지", href: "/category/악세사리?sub_category=반지" },
        { name: "팔찌", href: "/category/악세사리?sub_category=팔찌" }
      ]
    }
  ]
};

export default function Navigation() {
  const [isOpen, setIsOpen] = useState(false);
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const { themeConfig, tenantName } = useTheme();

  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    router.push(`/search?q=${encodeURIComponent(searchQuery.trim())}`);
    setIsSearchOpen(false);
    setSearchQuery("");
  };

  // 브랜드 목록 상태 및 카테고리 탭 상태 추가
  const [brands, setBrands] = useState<{ id: number; name: string; eng_name: string; slug: string; is_premium: boolean; category_group: string }[]>([]);
  const [isBrandOpen, setIsBrandOpen] = useState(false);
  const [activeBrandTab, setActiveBrandTab] = useState<"all" | "bag" | "shoes" | "watch">("all");

  useEffect(() => {
    async function fetchBrands() {
      try {
        const res = await fetch(`${API_URL}/api/products/brands`);
        if (res.ok) {
          setBrands(await res.json());
        }
      } catch (error) {
        console.warn("Failed to fetch brands for GNB", error);
      }
    }
    fetchBrands();
  }, []);

  if (pathname?.startsWith("/admin")) {
    return null;
  }

  // Get Border Radius Class Helper
  const getRadiusStyle = (r: string | undefined) => {
    if (r === "none") return "0px";
    if (r === "sm") return "4px";
    if (r === "md") return "8px";
    if (r === "lg") return "16px";
    if (r === "full") return "9999px";
    return "9999px"; // Default for pill button
  };

  const isVtonEnabled = themeConfig.features?.enable_vton !== false;
  const isCheckoutEnabled = themeConfig.features?.enable_checkout !== false;

  const filteredBrands = brands.filter((b: any) => {
    if (activeBrandTab === "all") {
      return b.category_group === "all";
    }
    return b.category_group && b.category_group.includes(activeBrandTab);
  });

  return (
    <nav className="fixed top-0 w-full z-50 glass-panel border-b border-white/20 flex flex-col">
      {/* 1차 프로모션 띠 배너 (Strip) */}
      {themeConfig.enablePromo !== false && themeConfig.promoText && (
        <Link 
          href={themeConfig.promoLinkUrl || "/register"}
          className="w-full h-8 flex items-center justify-center text-[11px] font-bold transition-all hover:brightness-110 tracking-tight shrink-0 select-none text-center px-4"
          style={{ 
            backgroundColor: themeConfig.promoBgColor || "#ef4444",
            color: themeConfig.promoTextColor || "#ffffff" 
          }}
        >
          {themeConfig.promoText}
        </Link>
      )}
      
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 w-full">
        <div className="flex justify-between items-center h-20">
          {/* Logo */}
          <div className="flex-shrink-0 flex items-center">
            <Link href="/" className="flex items-center">
              {themeConfig.logoUrl ? (
                <img src={themeConfig.logoUrl} alt={tenantName} className="h-10 object-contain" />
              ) : (
                <span 
                  className="text-2xl font-black tracking-tighter text-gray-900 dark:text-white uppercase"
                  style={{ fontFamily: themeConfig.fontFamily }}
                >
                  {tenantName}
                </span>
              )}
            </Link>
          </div>

          {/* Desktop Categories */}
          <div className="hidden md:flex gap-2 lg:gap-4 xl:gap-6 items-center shrink-0">
            
            {/* 브랜드관 드롭다운 메뉴 */}
            <div 
              className="relative py-2"
              onMouseEnter={() => setIsBrandOpen(true)}
              onMouseLeave={() => setIsBrandOpen(false)}
            >
              <button
                className="text-gray-700 dark:text-gray-300 font-bold hover:text-opacity-80 transition-colors flex items-center gap-1 cursor-pointer whitespace-nowrap"
              >
                브랜드관 <span className="text-[10px] opacity-75">▼</span>
              </button>
              <div 
                className="absolute bottom-0 w-full h-0.5 scale-x-0 transition-transform origin-left rounded-full" 
                style={{ 
                  backgroundColor: themeConfig.primaryColor || "#2563eb",
                  transform: isBrandOpen ? "scaleX(1)" : "scaleX(0)"
                }}
              />
              
              <AnimatePresence>
                {isBrandOpen && brands.length > 0 && (
                  <motion.div 
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 10 }}
                    className="absolute left-1/2 -translate-x-1/2 top-full pt-2 w-[600px] z-50"
                  >
                    <div className="bg-white/95 dark:bg-slate-900/95 backdrop-blur-lg border border-slate-200/50 dark:border-slate-800/50 rounded-2xl shadow-2xl p-4 flex gap-4 h-[350px]">
                      {/* Left Tab Menu */}
                      <div className="w-1/4 border-r border-slate-100 dark:border-slate-800 pr-2 flex flex-col gap-1 shrink-0 select-none">
                        <div className="text-[10px] font-bold text-slate-400 dark:text-slate-500 mb-2 px-2 uppercase tracking-wider">카테고리</div>
                        {[
                          { id: "all", label: "종합 명품" },
                          { id: "bag", label: "가방 / 지갑" },
                          { id: "shoes", label: "슈즈 에디션" },
                          { id: "watch", label: "럭셔리 워치" },
                        ].map((tab) => (
                          <button
                            key={tab.id}
                            onMouseEnter={() => setActiveBrandTab(tab.id as any)}
                            onClick={() => setActiveBrandTab(tab.id as any)}
                            className={`w-full text-left px-3 py-2 rounded-lg text-xs font-bold transition-all ${
                              activeBrandTab === tab.id
                                ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900"
                                : "text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800/50"
                            }`}
                          >
                            {tab.label}
                          </button>
                        ))}
                      </div>

                      {/* Right Brand Grid */}
                      <div className="w-3/4 flex flex-col h-full overflow-hidden">
                        <div className="text-[10px] font-bold text-slate-400 dark:text-slate-500 mb-2 uppercase tracking-wider flex justify-between">
                          <span>브랜드 목록</span>
                          <span>총 {filteredBrands.length}개</span>
                        </div>
                        <div className="grid grid-cols-2 gap-1.5 overflow-y-auto pr-1 flex-1 scrollbar-thin scrollbar-thumb-slate-200 dark:scrollbar-thumb-slate-800">
                          {filteredBrands.map((b) => (
                            <Link
                              key={b.slug}
                              href={`/brand/${b.slug}`}
                              onClick={() => setIsBrandOpen(false)}
                              className="flex items-center justify-between px-3 py-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-850 transition-colors group/brand-item"
                            >
                              <span className="text-xs font-bold text-slate-700 dark:text-slate-300 group-hover/brand-item:text-blue-600 dark:group-hover/brand-item:text-blue-400 transition-colors truncate mr-1">
                                {b.name}
                              </span>
                              <span className="text-[9px] text-slate-400 font-mono tracking-wider dark:text-slate-500 group-hover/brand-item:text-slate-600 dark:group-hover/brand-item:text-slate-355 transition-colors truncate shrink-0">
                                {b.eng_name.toUpperCase()}
                              </span>
                            </Link>
                          ))}
                        </div>
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {CATEGORIES.map((category) => (
              <motion.div key={category} whileHover={{ y: -2 }} className="relative group py-2">
                <Link
                  href={CATEGORY_MAP[category] || `/category/${category}`}
                  className="text-gray-700 dark:text-gray-300 font-medium hover:text-opacity-80 transition-colors whitespace-nowrap"
                >
                  {category}
                </Link>
                <div 
                  className="absolute bottom-0 w-full h-0.5 scale-x-0 group-hover:scale-x-100 transition-transform origin-left rounded-full" 
                  style={{ backgroundColor: themeConfig.primaryColor || "#2563eb" }}
                />

                {/* Premium 3-Level Hover Dropdown */}
                {NAV_SUB_CATEGORIES[category] && (
                  <div className="absolute left-1/2 -translate-x-1/2 top-full pt-2 w-56 opacity-0 translate-y-2 pointer-events-none group-hover:opacity-100 group-hover:translate-y-0 group-hover:pointer-events-auto transition-all duration-200 ease-out z-50">
                    <div className="bg-white/95 dark:bg-slate-900/95 backdrop-blur-lg border border-slate-200/50 dark:border-slate-800/50 rounded-2xl shadow-2xl p-2 space-y-1">
                      {NAV_SUB_CATEGORIES[category].map((subItem) => (
                        <div key={subItem.name} className="relative group/sub">
                          {subItem.children ? (
                            <div className="flex items-center justify-between px-4 py-2 text-sm font-semibold text-slate-700 dark:text-slate-300 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800/50 cursor-pointer transition-colors">
                              <span>{subItem.name}</span>
                              <span className="text-[10px] text-slate-400">▶</span>
                              
                              {/* 3rd Level (소분류) */}
                              <div className="absolute left-full top-0 pl-2 w-48 opacity-0 translate-x-2 pointer-events-none group-hover/sub:opacity-100 group-hover/sub:translate-x-0 group-hover/sub:pointer-events-auto transition-all duration-200">
                                <div className="bg-white/95 dark:bg-slate-900/95 backdrop-blur-lg border border-slate-200/50 dark:border-slate-800/50 rounded-xl shadow-xl p-1">
                                  {subItem.children.map((childItem) => (
                                    <Link
                                      key={childItem.name}
                                      href={childItem.href}
                                      className="block px-3 py-1.5 text-xs text-slate-600 hover:text-blue-600 dark:text-slate-400 dark:hover:text-blue-400 hover:bg-slate-50 dark:hover:bg-slate-800/50 rounded-md transition-colors"
                                    >
                                      {childItem.name}
                                    </Link>
                                  ))}
                                </div>
                              </div>
                            </div>
                          ) : (
                            <Link
                              href={subItem.href}
                              className="block px-4 py-2 text-sm text-slate-600 hover:text-blue-600 dark:text-slate-400 dark:hover:text-blue-400 hover:bg-slate-100 dark:hover:bg-slate-800/50 rounded-lg transition-colors"
                            >
                              {subItem.name}
                            </Link>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </motion.div>
            ))}

            {/* 1:1 문의 탭 추가 (작고 직관적인 아이콘 뱃지 스타일) */}
            <motion.div whileHover={{ y: -2 }} className="relative group border-l border-slate-300 dark:border-slate-850 pl-2 lg:pl-4 flex items-center shrink-0">
              <Link
                href="/mypage/support"
                className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200/80 dark:bg-slate-900 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-800 rounded-full text-xs font-bold text-slate-700 dark:text-slate-300 transition-all shadow-sm whitespace-nowrap"
              >
                <MessageSquare size={12} className="text-blue-500" />
                <span>1:1 문의</span>
              </Link>
            </motion.div>
          </div>

          {/* User Icons */}
          <div className="hidden md:flex items-center gap-3 lg:gap-6 text-gray-700 dark:text-gray-300 shrink-0 whitespace-nowrap">
            <button onClick={() => setIsSearchOpen(!isSearchOpen)} className="hover:text-opacity-80 transition shrink-0">
              {isSearchOpen ? <X size={22} /> : <Search size={22} />}
            </button>
            <div className="flex items-center gap-1.5 lg:gap-3 shrink-0 whitespace-nowrap">
              {user ? (
                <>
                  <Link href="/mypage" className="text-sm font-bold hover:underline shrink-0 whitespace-nowrap" style={{ color: themeConfig.primaryColor || "#2563eb" }}>
                    {user.name}님
                  </Link>
                  {user.role === "ADMIN" && (
                    <Link href="/admin" title="관리자 설정" className="hover:text-opacity-80 transition flex items-center shrink-0">
                      <Settings size={20} />
                    </Link>
                  )}
                  <button onClick={() => logout()} title="로그아웃" className="hover:text-red-500 transition shrink-0"><LogOut size={20} /></button>
                </>
              ) : (
                <Link href="/login" title="로그인/가입" className="hover:text-opacity-80 transition shrink-0"><User size={22} /></Link>
              )}
            </div>
            {isCheckoutEnabled && (
              <Link href="/cart" className="hover:text-opacity-80 transition relative shrink-0">
                <ShoppingBag size={22} />
              </Link>
            )}
          </div>

          {/* Mobile menu button */}
          <div className="md:hidden flex items-center gap-4">
            {isCheckoutEnabled && (
              <Link href="/cart" className="text-gray-750 dark:text-gray-250 hover:text-opacity-80 transition relative shrink-0">
                <ShoppingBag size={22} />
              </Link>
            )}
            <button onClick={() => setIsSearchOpen(!isSearchOpen)} className="text-gray-750 dark:text-gray-250 hover:text-opacity-80 transition shrink-0">
              {isSearchOpen ? <X size={22} /> : <Search size={22} />}
            </button>
            <button onClick={() => setIsOpen(!isOpen)} className="text-gray-750 dark:text-gray-250">
              {isOpen ? <X size={28} /> : <Menu size={28} />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Menu */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="md:hidden glass-panel border-t border-white/10"
          >
            <div className="px-4 py-6 space-y-4 flex flex-col">
              {/* 모바일 상시 검색창 */}
              <form onSubmit={handleSearchSubmit} className="relative w-full">
                <Search size={16} className="absolute left-3.5 top-3.5 text-slate-400" />
                <input
                  type="text"
                  placeholder="상품명을 검색해 보세요..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl pl-10 pr-4 py-2.5 text-sm text-slate-800 dark:text-white placeholder-slate-400 focus:outline-none focus:border-blue-500 transition-colors"
                />
              </form>

              {isVtonEnabled && (
                <button
                  onClick={() => {
                    setIsOpen(false);
                    alert("곧 구현될 예정입니다.");
                  }}
                  className="text-lg font-bold text-white shadow-lg flex items-center gap-2 w-full text-left"
                  style={{ 
                    backgroundImage: `linear-gradient(135deg, ${themeConfig.primaryColor || "#2563eb"}, ${themeConfig.secondaryColor || "#4f46e5"})`,
                    borderRadius: getRadiusStyle(themeConfig.borderRadius),
                    padding: "12px 16px"
                  }}
                >
                  ✨ Premium AI Fitting
                </button>
              )}
              {user?.role === "ADMIN" && (
                <Link
                  href="/admin"
                  onClick={() => setIsOpen(false)}
                  className="text-lg font-bold border rounded-xl px-4 py-3 bg-blue-50/50 dark:bg-blue-950/20 shadow-sm flex items-center gap-2 justify-center"
                  style={{ 
                    borderColor: `${themeConfig.primaryColor}33` || "rgba(37,99,235,0.2)",
                    color: themeConfig.primaryColor || "#2563eb"
                  }}
                >
                  ⚙️ 관리자 설정 페이지
                </Link>
              )}
              
              {/* 모바일 브랜드 메뉴 */}
              {brands.length > 0 && (
                <div className="border-b border-slate-200 dark:border-slate-800 pb-4 mb-2">
                  <div className="text-sm font-bold text-slate-400 dark:text-slate-500 mb-2 flex justify-between items-center">
                    <span>인기 브랜드관</span>
                    <div className="flex gap-1">
                      {[
                        { id: "all", label: "종합" },
                        { id: "bag", label: "가방" },
                        { id: "shoes", label: "신발" },
                        { id: "watch", label: "시계" },
                      ].map((t) => (
                        <button
                          key={t.id}
                          onClick={() => setActiveBrandTab(t.id as any)}
                          className={`px-2 py-0.5 text-[10px] font-bold rounded-md ${
                            activeBrandTab === t.id
                              ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900"
                              : "bg-slate-105 text-slate-500 dark:bg-slate-800 text-slate-600 dark:text-slate-400"
                          }`}
                        >
                          {t.label}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-2 max-h-48 overflow-y-auto pr-1">
                    {brands
                      .filter((b: any) => {
                        if (activeBrandTab === "all") return b.category_group === "all";
                        return b.category_group && b.category_group.includes(activeBrandTab);
                      })
                      .map((b) => (
                        <Link
                          key={b.slug}
                          href={`/brand/${b.slug}`}
                          onClick={() => setIsOpen(false)}
                          className="px-3 py-2 text-xs font-bold text-slate-700 dark:text-slate-300 bg-slate-100/50 dark:bg-slate-900/50 rounded-lg border border-slate-200/20 dark:border-slate-800/20 hover:bg-slate-100 dark:hover:bg-slate-850 transition-colors flex flex-col"
                        >
                          <span>{b.name}</span>
                          <span className="text-[8px] font-normal opacity-75 text-slate-400 truncate">{b.eng_name}</span>
                        </Link>
                      ))}
                  </div>
                </div>
              )}

              {CATEGORIES.map((category) => (
                <Link
                  key={category}
                  href={CATEGORY_MAP[category] || `/category/${category}`}
                  onClick={() => setIsOpen(false)}
                  className="text-lg font-semibold text-gray-800 dark:text-gray-200"
                >
                  {category}
                </Link>
              ))}
              
              {/* 모바일 1:1 문의 추가 */}
              <Link
                href="/mypage/support"
                onClick={() => setIsOpen(false)}
                className="text-sm font-bold text-slate-700 dark:text-slate-300 border-t border-slate-200 dark:border-slate-850 pt-4 flex items-center gap-2 justify-center py-2.5 bg-slate-100 dark:bg-slate-900 rounded-xl border border-slate-200/50 dark:border-slate-850 mt-1"
              >
                <MessageSquare size={14} className="text-blue-500 animate-pulse" />
                <span>1:1 고객 문의하기</span>
              </Link>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      
      {/* 2차 검색창 드롭다운 (애니메이션 슬라이드) */}
      <AnimatePresence>
        {isSearchOpen && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="w-full bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 py-3 px-4 shadow-lg"
          >
            <form onSubmit={handleSearchSubmit} className="max-w-3xl mx-auto flex items-center gap-2">
              <Search className="text-slate-400 shrink-0" size={20} />
              <input
                type="text"
                placeholder="찾으시는 프리미엄 상품명을 입력하세요..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="flex-1 bg-transparent border-none focus:outline-none focus:ring-0 text-sm text-slate-800 dark:text-white placeholder-slate-400"
                autoFocus
              />
              <button
                type="submit"
                className="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold rounded-lg transition-colors shadow-md"
              >
                검색
              </button>
            </form>
          </motion.div>
        )}
      </AnimatePresence>
    </nav>
  );
}