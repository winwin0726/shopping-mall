"use client";

import { useAuth } from "@/hooks/useAuth";
import { useRouter, usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Loader2, LayoutDashboard, Package, Settings, Camera, LogOut, Ticket, Star, Heart, MapPin, MessageSquare, Edit3 } from "lucide-react";

const GRADE_LABELS: Record<number, string> = {
  0: "관리자 (ADMIN)",
  1: "VVIP (적립 5%)",
  2: "VIP (적립 3%)",
  3: "우수회원 (적립 2%)",
  4: "일반회원 (적립 1%)",
  5: "미가입회원",
};

export default function MyPageLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [isClient, setIsClient] = useState(false);

  useEffect(() => {
    setIsClient(true);
    if (!loading && !user) {
      router.push("/login");
      return;
    }

    // 5등급(미가입) 회원 통제 룰: 대시보드, support, settings, orders 외의 접근 차단
    if (!loading && user && user.grade === 5) {
      const allowedPaths = ["/mypage", "/mypage/support", "/mypage/settings", "/mypage/orders"];
      if (!allowedPaths.includes(pathname)) {
        alert("승인 대기 상태(미가입회원)에서는 해당 기능을 이용하실 수 없습니다.");
        router.push("/mypage");
      }
    }
  }, [user, loading, router, pathname]);

  if (loading || !isClient) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-900">
        <Loader2 className="animate-spin text-slate-400" size={32} />
      </div>
    );
  }

  if (!user) return null;

  const NAVIGATION = [
    { name: "대시보드", href: "/mypage", icon: LayoutDashboard },
    { name: "주문 내역", href: "/mypage/orders", icon: Package },
    { name: "AI 스튜디오", href: "/mypage/ai-studio", icon: Camera },
    { name: "위시리스트", href: "/mypage/wishlist", icon: Heart },
    { name: "배송지 관리", href: "/mypage/addresses", icon: MapPin },
    { name: "나의 리뷰", href: "/mypage/reviews", icon: Edit3 },
    { name: "1:1 문의", href: "/mypage/support", icon: MessageSquare },
    { name: "계정 설정", href: "/mypage/settings", icon: Settings },
  ];

  return (
    <div className="min-h-screen bg-[#F8FAFC] dark:bg-[#0F172A] pt-24 pb-12 sm:pt-32">
      <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col lg:flex-row gap-8">
          
          {/* Left Sidebar */}
          <aside className="w-full lg:w-72 flex-shrink-0">
            {/* User Mini Profile Card */}
            <div className="bg-white dark:bg-slate-800 rounded-2xl p-6 shadow-sm border border-slate-200/60 dark:border-slate-700 mb-6">
              <div className="flex items-center space-x-4 mb-6">
                <div className="w-14 h-14 rounded-full bg-gradient-to-br from-blue-600 to-indigo-600 flex flex-col items-center justify-center text-white text-xl font-bold shadow-md overflow-hidden ring-2 ring-white dark:ring-slate-800">
                  {user.profile_image ? (
                    <img src={user.profile_image.startsWith('http') ? user.profile_image : `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}${user.profile_image}`} alt="프로필" className="w-full h-full object-cover" />
                  ) : (
                    user.name.charAt(0)
                  )}
                </div>
                <div>
                  <h2 className="text-lg font-bold text-slate-900 dark:text-white leading-tight">{user.name}</h2>
                  <p className="text-xs font-semibold text-slate-500 mt-1 uppercase tracking-wider flex items-center">
                    <Star size={12} className="mr-1 text-amber-500 fill-amber-500" />
                    {GRADE_LABELS[user.grade ?? 4]}
                  </p>
                </div>
              </div>
              
              {/* Point & Coupon */}
              <div className="grid grid-cols-2 gap-3 border-t border-slate-100 dark:border-slate-700/50 pt-5">
                <div className="bg-slate-50 dark:bg-slate-900/50 p-3 rounded-xl border border-slate-100 dark:border-slate-700/50">
                  <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1">적립금</p>
                  <p className="text-sm font-extrabold text-slate-800 dark:text-slate-200">{(user.reward_points ?? 0).toLocaleString()}원</p>
                </div>
                <div className="bg-slate-50 dark:bg-slate-900/50 p-3 rounded-xl border border-slate-100 dark:border-slate-700/50">
                  <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1 flex items-center"><Ticket size={10} className="mr-1" /> Coupon</p>
                  <p className="text-sm font-extrabold text-blue-600 dark:text-blue-400">{(user.coupon_count ?? 0).toLocaleString()}장</p>
                </div>
              </div>
            </div>

            {/* Navigation Menu */}
            <nav className="bg-white dark:bg-slate-800 rounded-2xl shadow-sm border border-slate-200/60 dark:border-slate-700 p-3">
              <ul className="space-y-1">
                {NAVIGATION.map((item) => {
                  const isActive = pathname === item.href;
                  const isRestricted = user.grade === 5 && !["/mypage", "/mypage/support", "/mypage/settings", "/mypage/orders"].includes(item.href);
                  
                  return (
                    <li key={item.name}>
                      <Link 
                        href={isRestricted ? "#" : item.href}
                        onClick={(e) => {
                          if (isRestricted) {
                            e.preventDefault();
                            alert("승인 대기 상태(미가입회원)에서는 이 기능을 이용하실 수 없습니다.");
                          }
                        }}
                        className={`flex items-center space-x-3 px-4 py-3.5 rounded-xl transition-all relative overflow-hidden group ${
                          isActive 
                            ? "text-blue-700 dark:text-blue-400 font-bold bg-blue-50/50 dark:bg-blue-900/20" 
                            : isRestricted
                              ? "text-slate-300 dark:text-slate-600 cursor-not-allowed opacity-50"
                              : "text-slate-500 dark:text-slate-400 font-medium hover:bg-slate-50 dark:hover:bg-slate-700/50 hover:text-slate-900 dark:hover:text-slate-200"
                        }`}
                      >
                        {isActive && (
                          <motion.div 
                            layoutId="active-nav-indicator"
                            className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-1/2 bg-blue-600 dark:bg-blue-500 rounded-r-full"
                          />
                        )}
                        <item.icon size={20} className={isActive ? "text-blue-600 dark:text-blue-500" : isRestricted ? "opacity-40" : "group-hover:scale-110 transition-transform"} />
                        <span>{item.name} {isRestricted && "🔒"}</span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
              
              <div className="mt-8 pt-4 border-t border-slate-100 dark:border-slate-700/50">
                <button 
                  onClick={() => logout()}
                  className="w-full flex items-center space-x-3 px-4 py-3 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-xl transition-colors font-semibold"
                >
                  <LogOut size={20} />
                  <span>로그아웃</span>
                </button>
              </div>
            </nav>
          </aside>

          {/* Right Content Area */}
          <main className="flex-1 w-full min-w-0">
            {children}
          </main>

        </div>
      </div>
    </div>
  );
}
