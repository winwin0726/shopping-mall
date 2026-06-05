"use client";

import { useAuth } from "@/hooks/useAuth";
import { MoveRight, Package, TrendingUp, Sparkles, Camera, AlertCircle } from "lucide-react";
import Link from "next/link";
import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { useTheme } from "@/components/ThemeProvider";

const GRADE_LABELS: Record<number, string> = {
  0: "관리자 (ADMIN)",
  1: "VVIP 회원 (적립 5%)",
  2: "VIP 회원 (적립 3%)",
  3: "우수 회원 (적립 2%)",
  4: "일반 회원 (적립 1%)",
  5: "가입 승인 대기 (미가입)",
};

export default function MyPageOverview() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";
  const { user } = useAuth();
  const [ordersCount, setOrdersCount] = useState(0);
  const { themeConfig, tenantName } = useTheme();

  useEffect(() => {
    // 최근 주문 요약 API 호출 (더미 데이터)
    const fetchOrders = async () => {
      const token = localStorage.getItem("token");
      try {
        const res = await fetch(`${apiUrl}/api/orders/me/orders`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (res.ok) {
          const data = await res.json();
          setOrdersCount(data.length);
        }
      } catch (err) {
        console.error(err);
      }
    };
    fetchOrders();
  }, []);

  const container = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: { staggerChildren: 0.1 }
    }
  };

  const item = {
    hidden: { opacity: 0, y: 20 },
    show: { opacity: 1, y: 0, transition: { type: "spring" as const, stiffness: 300, damping: 24 } }
  };

  return (
    <motion.div 
      variants={container}
      initial="hidden"
      animate="show"
      className="space-y-6"
    >
      {/* 5등급(미가입) 회원 전용 가입 대기 안내 배너 */}
      {user?.grade === 5 && (
        <motion.div variants={item} className="bg-gradient-to-r from-amber-600 to-amber-700 rounded-3xl p-6 text-white shadow-lg border border-amber-500/20 flex items-center space-x-4">
          <AlertCircle size={36} className="text-white flex-shrink-0 animate-pulse" />
          <div>
            <h2 className="text-lg font-bold">회원 가입 승인 대기 중</h2>
            <p className="text-sm text-amber-100 mt-1">
              현재 가입 승인 대기 상태(미가입회원)입니다. 본사 관리자의 최종 승인 이후 상품의 가격 열람 및 결제, AI 피팅룸 이용이 가능합니다.
            </p>
          </div>
        </motion.div>
      )}

      {/* Welcome Banner */}
      <motion.div variants={item} className="bg-gradient-to-r from-blue-900 to-indigo-900 rounded-3xl p-8 sm:p-10 relative overflow-hidden shadow-2xl">
        <div className="absolute inset-0 bg-[url('/noise.png')] opacity-20 mix-blend-overlay"></div>
        <div className="absolute top-0 right-0 w-64 h-64 bg-white/10 blur-3xl rounded-full -translate-y-1/2 translate-x-1/3"></div>
        
        <div className="relative z-10">
          <div className="inline-block bg-white/20 text-white border border-white/30 text-xs px-3 py-1 rounded-full font-bold mb-4 backdrop-blur-sm">
            등급: {GRADE_LABELS[user?.grade ?? 4]}
          </div>
          
          <h1 className="text-3xl sm:text-4xl font-extrabold text-white mb-2 leading-tight">
            환영합니다, {user?.name}님! <Sparkles className="inline-block ml-2 text-yellow-400" size={28} />
          </h1>
          <p className="text-indigo-200 text-sm sm:text-base font-medium max-w-xl">
            {tenantName} AI 스타일 스튜디오에 오신 것을 환영합니다. 스마트한 위시리스트와 AI 피팅룸으로 나만의 스타일을 완성해보세요.
          </p>
          
          <div className="mt-8 flex flex-wrap gap-4">
            <Link href="/products" className="bg-white text-indigo-900 px-6 py-3 rounded-xl font-bold text-sm hover:scale-105 transition-transform shadow-lg shadow-white/10 flex items-center">
              쇼핑 계속하기 <MoveRight size={16} className="ml-2" />
            </Link>
          </div>
        </div>
      </motion.div>

      {/* Stats Widgets */}
      <motion.div variants={item} className="grid grid-cols-1 sm:grid-cols-3 gap-6">
        <div className="bg-white dark:bg-slate-800 rounded-3xl p-6 shadow-sm border border-slate-200/60 dark:border-slate-700/50 flex flex-col justify-between">
          <div className="w-12 h-12 rounded-2xl bg-indigo-50 dark:bg-indigo-900/30 flex items-center justify-center text-indigo-600 dark:text-indigo-400 mb-4">
            <Package size={24} />
          </div>
          <div>
            <p className="text-sm font-bold text-slate-500 mb-1">최근 주문 건수</p>
            <h3 className="text-3xl font-black text-slate-900 dark:text-white">{ordersCount}건</h3>
          </div>
        </div>

        <div className="bg-white dark:bg-slate-800 rounded-3xl p-6 shadow-sm border border-slate-200/60 dark:border-slate-700/50 flex flex-col justify-between">
          <div className="w-12 h-12 rounded-2xl bg-amber-50 dark:bg-amber-900/30 flex items-center justify-center text-amber-600 dark:text-amber-400 mb-4">
            <TrendingUp size={24} />
          </div>
          <div>
            <p className="text-sm font-bold text-slate-500 mb-1">보유 적립금</p>
            <h3 className="text-3xl font-black text-slate-900 dark:text-white">
              {(user?.reward_points ?? 0).toLocaleString()} <span className="text-lg text-slate-400 font-medium">원</span>
            </h3>
          </div>
        </div>

        <Link href="/mypage/wishlist" className="bg-white dark:bg-slate-800 rounded-3xl p-6 shadow-sm border border-slate-200/60 dark:border-slate-700/50 flex flex-col justify-between hover:border-blue-500/50 transition-colors cursor-pointer relative overflow-hidden group">
          <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-purple-500/5 opacity-0 group-hover:opacity-100 transition-opacity"></div>
          <div className="relative z-10 w-12 h-12 rounded-2xl bg-blue-50 dark:bg-blue-900/30 flex items-center justify-center text-blue-600 dark:text-blue-400 mb-4">
            <Camera size={24} />
          </div>
          <div className="relative z-10">
            <p className="text-sm font-bold text-slate-500 mb-1">AI 위시리스트</p>
            <h3 className="text-xl font-bold text-slate-900 dark:text-white flex items-center">
              위시리스트 바로가기 <MoveRight size={18} className="ml-2 group-hover:translate-x-1 transition-transform" />
            </h3>
          </div>
        </Link>
      </motion.div>

      {/* Recent Orders Shortcut */}
      <motion.div variants={item} className="bg-white dark:bg-slate-800 rounded-3xl p-8 shadow-sm border border-slate-200/60 dark:border-slate-700/50">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-bold text-slate-900 dark:text-white">최근 주문 내역</h2>
          <Link href="/mypage/orders" className="text-sm font-bold text-blue-600 hover:text-blue-700 dark:text-blue-400">
            전체 내역 보기
          </Link>
        </div>
        
        {ordersCount === 0 ? (
          <div className="text-center py-12 bg-slate-50 dark:bg-slate-900/50 rounded-2xl border border-dashed border-slate-200 dark:border-slate-700">
            <Package className="mx-auto text-slate-300 dark:text-slate-600 mb-3" size={32} />
            <p className="text-slate-500 font-medium text-sm">최근 1개월 내 주문 내역이 없습니다.</p>
          </div>
        ) : (
          <div className="text-center py-12 bg-slate-50 dark:bg-slate-900/50 rounded-2xl border border-dashed border-slate-200 dark:border-slate-700">
            <p className="text-slate-500 font-medium text-sm">주문 관련 세부 내역은 전체 내역 보기에서 확인하실 수 있습니다.</p>
          </div>
        )}
      </motion.div>

    </motion.div>
  );
}
