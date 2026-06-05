"use client";

import Link from "next/link";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ShoppingBag, Search, Menu, X, User, LogOut, Settings, MessageSquare } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { usePathname } from "next/navigation";
import { useTheme } from "@/components/ThemeProvider";

const CATEGORIES = [
  "남성의류", "여성의류", "가방", "지갑", "시계", "악세사리", "신발", "국내배송"
];

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
  "가방": [
    { name: "토트백", href: "/category/가방?sub_category=토트백" },
    { name: "크로스백", href: "/category/가방?sub_category=크로스백" },
    { name: "백팩", href: "/category/가방?sub_category=백팩" }
  ],
  "지갑": [
    { name: "반지갑", href: "/category/지갑?sub_category=반지갑" },
    { name: "장지갑", href: "/category/지갑?sub_category=장지갑" }
  ],
  "시계": [
    { name: "메탈시계", href: "/category/시계?sub_category=메탈시계" },
    { name: "가죽시계", href: "/category/시계?sub_category=가죽시계" }
  ],
  "악세사리": [
    { name: "목걸이", href: "/category/악세사리?sub_category=목걸이" },
    { name: "반지", href: "/category/악세사리?sub_category=반지" },
    { name: "팔찌", href: "/category/악세사리?sub_category=팔찌" }
  ]
};

export default function Navigation() {
  const [isOpen, setIsOpen] = useState(false);
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const { themeConfig, tenantName } = useTheme();

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
          <div className="hidden md:flex space-x-8 items-center">
            {isVtonEnabled && (
              <motion.div whileHover={{ y: -2 }} className="relative group mr-2">
                <Link 
                  href="/fitting-room" 
                  className="px-4 py-1.5 text-white font-bold text-sm shadow-md hover:shadow-lg transition flex items-center gap-1"
                  style={{ 
                    backgroundColor: themeConfig.primaryColor || "#2563eb",
                    borderRadius: getRadiusStyle(themeConfig.borderRadius)
                  }}
                >
                  ✨ AI Fitting
                </Link>
              </motion.div>
            )}
            
            {CATEGORIES.map((category) => (
              <motion.div key={category} whileHover={{ y: -2 }} className="relative group py-2">
                <Link
                  href={`/category/${category}`}
                  className="text-gray-700 dark:text-gray-300 font-medium hover:text-opacity-80 transition-colors"
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
            <motion.div whileHover={{ y: -2 }} className="relative group ml-4 border-l border-slate-300 dark:border-slate-850 pl-4 flex items-center">
              <Link
                href="/mypage/support"
                className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200/80 dark:bg-slate-900 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-800 rounded-full text-xs font-bold text-slate-700 dark:text-slate-300 transition-all shadow-sm"
              >
                <MessageSquare size={12} className="text-blue-500" />
                <span>1:1 문의</span>
              </Link>
            </motion.div>
          </div>

          {/* User Icons */}
          <div className="hidden md:flex items-center space-x-6 text-gray-700 dark:text-gray-300">
            <button onClick={() => alert("검색 기능은 준비 중입니다. 조만간 추가될 예정입니다!")} className="hover:text-opacity-80 transition"><Search size={22} /></button>
            <div className="flex items-center space-x-3">
              {user ? (
                <>
                  <Link href="/mypage" className="text-sm font-bold hover:underline" style={{ color: themeConfig.primaryColor || "#2563eb" }}>
                    {user.name}님
                  </Link>
                  {user.role === "ADMIN" && (
                    <Link href="/admin" title="관리자 설정" className="hover:text-opacity-80 transition flex items-center">
                      <Settings size={20} />
                    </Link>
                  )}
                  <button onClick={() => logout()} title="로그아웃" className="hover:text-red-500 transition"><LogOut size={20} /></button>
                </>
              ) : (
                <Link href="/login" title="로그인/가입" className="hover:text-opacity-80 transition"><User size={22} /></Link>
              )}
            </div>
            {isCheckoutEnabled && (
              <Link href="/cart" className="hover:text-opacity-80 transition relative">
                <ShoppingBag size={22} />
              </Link>
            )}
          </div>

          {/* Mobile menu button */}
          <div className="md:hidden flex items-center">
            <button onClick={() => setIsOpen(!isOpen)} className="text-gray-700 dark:text-gray-300">
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
              {isVtonEnabled && (
                <Link
                  href="/fitting-room"
                  onClick={() => setIsOpen(false)}
                  className="text-lg font-bold text-white shadow-lg flex items-center gap-2"
                  style={{ 
                    backgroundImage: `linear-gradient(135deg, ${themeConfig.primaryColor || "#2563eb"}, ${themeConfig.secondaryColor || "#4f46e5"})`,
                    borderRadius: getRadiusStyle(themeConfig.borderRadius),
                    padding: "12px 16px"
                  }}
                >
                  ✨ Premium AI Fitting
                </Link>
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
              {CATEGORIES.map((category) => (
                <Link
                  key={category}
                  href={`/category/${category}`}
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
    </nav>
  );
}