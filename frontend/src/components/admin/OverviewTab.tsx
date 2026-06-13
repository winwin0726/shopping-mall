"use client";
import { authFetch, API_URL } from "@/lib/api";

import { useEffect, useState } from "react";
import {
  BarChart3, TrendingUp, TrendingDown, DollarSign, ShoppingCart,
  Package, Loader2, AlertCircle, Users, Clock, ArrowRight,
  CheckCircle, XCircle, Hourglass, UserPlus, Zap
} from "lucide-react";

interface Stats {
  revenue: number;
  order_count: number;
  avg_order_value: number;
  pending_count: number;
  revenue_trend: string;
  order_trend: string;
}

interface RecentOrder {
  id: number;
  order_number: string;
  customer_name: string;
  total_amount: number;
  payment_status: string;
  created_at: string;
  summary_name: string;
}

interface RecentUser {
  id: number;
  email: string;
  name: string;
  role: string;
  created_at: string | null;
}

interface ProductDistribution {
  [key: string]: number;
}

export default function OverviewTab() {
  const apiUrl = API_URL;
  const [stats, setStats] = useState<Stats | null>(null);
  const [orders, setOrders] = useState<RecentOrder[]>([]);
  const [recentUsers, setRecentUsers] = useState<RecentUser[]>([]);
  const [productDist, setProductDist] = useState<ProductDistribution>({});
  const [userCount, setUserCount] = useState(0);
  const [productCount, setProductCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchAll = async () => {
      setLoading(true);
      setError(null);
      try {
        const [statsRes, ordersRes, usersRes, productsRes, distRes, recentUsersRes] = await Promise.all([
          authFetch(`${apiUrl}/api/orders/admin/orders/stats`),
          authFetch(`${apiUrl}/api/orders/admin/orders`),
          authFetch(`${apiUrl}/api/admin/users`),
          authFetch(`${apiUrl}/api/admin/products`),
          authFetch(`${apiUrl}/api/admin/stats/product-distribution`),
          authFetch(`${apiUrl}/api/admin/stats/recent-users`),
        ]);

        if (!statsRes.ok) throw new Error("통계 데이터를 불러올 수 없습니다.");
        setStats(await statsRes.json());

        if (ordersRes.ok) {
          const ordersData = await ordersRes.json();
          setOrders(ordersData.slice(0, 5));
        }
        if (usersRes.ok) {
          setUserCount((await usersRes.json()).length);
        }
        if (productsRes.ok) {
          setProductCount((await productsRes.json()).length);
        }
        if (distRes.ok) {
          setProductDist(await distRes.json());
        }
        if (recentUsersRes.ok) {
          setRecentUsers(await recentUsersRes.json());
        }
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center p-24 text-slate-500">
        <Loader2 size={48} className="animate-spin text-blue-500 mb-4" />
        <p>대시보드 데이터 불러오는 중...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-800 p-6 rounded-xl flex items-center shadow-sm">
        <AlertCircle className="mr-3 text-red-500 shrink-0" size={24} />
        <div>
          <p className="font-bold">데이터 로드 실패</p>
          <p className="text-sm mt-1">{error}</p>
        </div>
      </div>
    );
  }

  // 상품 분포 계산
  const totalProducts = Object.values(productDist).reduce((a, b) => a + b, 0);
  const approved = productDist["APPROVED"] || 0;
  const pending = productDist["PENDING"] || 0;
  const rejected = productDist["REJECTED"] || 0;

  const statusBadge = (status: string) => {
    const map: Record<string, { bg: string; text: string; border: string; label: string }> = {
      PAID: { bg: "bg-emerald-50", text: "text-emerald-700", border: "border-emerald-200", label: "결제완료" },
      PENDING: { bg: "bg-yellow-50", text: "text-yellow-750", border: "border-yellow-250", label: "대기" },
      CANCELLED: { bg: "bg-red-50", text: "text-red-700", border: "border-red-200", label: "취소" },
    };
    const s = map[status] || { bg: "bg-slate-150", text: "text-slate-700", border: "border-slate-200", label: status };
    return <span className={`px-2.5 py-1 rounded-full text-xs font-bold border ${s.bg} ${s.text} ${s.border}`}>{s.label}</span>;
  };

  const cards = [
    {
      label: "총 매출",
      value: `₩${(stats?.revenue || 0).toLocaleString()}`,
      icon: <DollarSign size={22} />,
      trend: stats?.revenue_trend,
      iconBg: "bg-blue-50 text-blue-600 border border-blue-100",
      ring: "ring-blue-500/5",
    },
    {
      label: "결제된 주문",
      value: `${stats?.order_count || 0}건`,
      icon: <ShoppingCart size={22} />,
      trend: stats?.order_trend,
      iconBg: "bg-emerald-50 text-emerald-600 border border-emerald-100",
      ring: "ring-emerald-500/5",
    },
    {
      label: "평균 주문금액",
      value: `₩${(stats?.avg_order_value || 0).toLocaleString()}`,
      icon: <BarChart3 size={22} />,
      iconBg: "bg-violet-50 text-violet-600 border border-violet-100",
      ring: "ring-violet-500/5",
    },
    {
      label: "파이프라인 대기",
      value: `${stats?.pending_count || 0}건`,
      icon: <Hourglass size={22} />,
      iconBg: "bg-amber-50 text-amber-600 border border-amber-100",
      ring: "ring-amber-500/5",
    },
    {
      label: "가입 회원수",
      value: `${userCount}명`,
      icon: <Users size={22} />,
      iconBg: "bg-pink-50 text-pink-600 border border-pink-100",
      ring: "ring-pink-500/5",
    },
    {
      label: "등록 상품수",
      value: `${productCount}개`,
      icon: <Package size={22} />,
      iconBg: "bg-cyan-50 text-cyan-600 border border-cyan-100",
      ring: "ring-cyan-500/5",
    },
  ];

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      {/* 제목 + 라이브 표시 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 mb-1 tracking-tight">대시보드 (Overview)</h2>
          <p className="text-slate-500 text-sm">쇼핑몰의 주요 통계와 현황을 한눈에 파악합니다.</p>
        </div>
        <div className="flex items-center gap-2 bg-emerald-50 border border-emerald-200 px-4 py-2 rounded-full">
          <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse" />
          <span className="text-xs font-bold text-emerald-700">LIVE</span>
        </div>
      </div>

      {/* ═══ KPI 통계 카드 그리드 ═══ */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {cards.map((card, i) => (
          <div
            key={i}
            className="bg-white border border-slate-200 rounded-2xl p-5 hover:border-slate-350 transition-all duration-300 group shadow-sm"
          >
            <div className="flex items-center justify-between mb-3">
              <div className={`w-11 h-11 rounded-xl flex items-center justify-center ${card.iconBg}`}>
                {card.icon}
              </div>
              {card.trend && (
                <div className={`flex items-center text-xs font-bold px-2 py-1 rounded-full border ${card.trend === "up" ? "text-emerald-700 bg-emerald-50 border-emerald-200" : "text-red-700 bg-red-50 border-red-200"}`}>
                  {card.trend === "up" ? <TrendingUp size={12} className="mr-1" /> : <TrendingDown size={12} className="mr-1" />}
                  {card.trend === "up" ? "상승" : "하락"}
                </div>
              )}
            </div>
            <p className="text-xs text-slate-500 font-semibold mb-1 uppercase tracking-wider">{card.label}</p>
            <p className="text-2xl font-extrabold text-slate-900 tracking-tight">{card.value}</p>
          </div>
        ))}
      </div>

      {/* ═══ 중간: 상품 분포 + 최근 가입 회원 ═══ */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 상품 상태 분포 차트 */}
        <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-violet-50 text-violet-600 flex items-center justify-center border border-violet-100">
                <Package size={20} />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-900">상품 상태 분포</h3>
                <p className="text-xs text-slate-500">전체 {totalProducts}개 상품</p>
              </div>
            </div>
          </div>

          {totalProducts === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 text-slate-400">
              <Package size={32} className="mb-2" />
              <p className="text-sm">등록된 상품이 없습니다</p>
            </div>
          ) : (
            <div className="space-y-4">
              {[
                { label: "승인됨", value: approved, color: "bg-emerald-500", textColor: "text-emerald-700", icon: <CheckCircle size={14} /> },
                { label: "대기중", value: pending, color: "bg-amber-500", textColor: "text-amber-700", icon: <Hourglass size={14} /> },
                { label: "반려됨", value: rejected, color: "bg-red-500", textColor: "text-red-600", icon: <XCircle size={14} /> },
              ].map((item, idx) => {
                const pct = totalProducts > 0 ? (item.value / totalProducts) * 100 : 0;
                return (
                  <div key={idx}>
                    <div className="flex items-center justify-between mb-1.5">
                      <div className={`flex items-center gap-1.5 text-xs font-bold ${item.textColor}`}>
                        {item.icon}
                        {item.label}
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-slate-500">{item.value}개</span>
                        <span className={`text-xs font-extrabold ${item.textColor}`}>{pct.toFixed(0)}%</span>
                      </div>
                    </div>
                    <div className="h-3 bg-slate-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full ${item.color} rounded-full transition-all duration-700 ease-out`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
              <div className="flex items-center justify-center gap-6 pt-4 border-t border-slate-100">
                {[
                  { label: "승인", value: approved, color: "border-emerald-500" },
                  { label: "대기", value: pending, color: "border-amber-500" },
                  { label: "반려", value: rejected, color: "border-red-500" },
                ].map((item, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <div className={`w-3 h-3 rounded-full border-2 ${item.color}`} />
                    <span className="text-xs text-slate-500">{item.label}: <span className="text-slate-900 font-extrabold">{item.value}</span></span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* 최근 가입 회원 */}
        <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-pink-50 text-pink-600 flex items-center justify-center border border-pink-100">
                <UserPlus size={20} />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-900">최근 가입 회원</h3>
                <p className="text-xs text-slate-500">신규 회원 현황</p>
              </div>
            </div>
          </div>

          {recentUsers.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 text-slate-400">
              <Users size={32} className="mb-2" />
              <p className="text-sm">가입된 회원이 없습니다</p>
            </div>
          ) : (
            <div className="space-y-3">
              {recentUsers.map((u) => (
                <div
                  key={u.id}
                  className="flex items-center justify-between p-3 bg-slate-50 rounded-xl hover:bg-slate-100/70 border border-slate-100/50 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-full bg-gradient-to-br from-blue-500 to-indigo-500 flex items-center justify-center text-white text-xs font-bold shadow-sm">
                      {u.name?.charAt(0)?.toUpperCase() || u.email?.charAt(0)?.toUpperCase() || "?"}
                    </div>
                    <div>
                      <p className="text-sm font-bold text-slate-800">{u.name || u.email}</p>
                      <p className="text-xs text-slate-500">{u.email}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-bold border ${u.role === "ADMIN" ? "bg-purple-50 text-purple-700 border-purple-200" : "bg-blue-50 text-blue-700 border-blue-200"}`}>
                      {u.role || "USER"}
                    </span>
                    {u.created_at && (
                      <p className="text-[10px] text-slate-500 mt-1 font-medium">
                        {new Date(u.created_at).toLocaleDateString()}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ═══ 빠른 액션 버튼 ═══ */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[
          { label: "AI 파이프라인 확인", desc: "크롤러 수집 대기 상품 처리", icon: <Zap size={20} />, color: "from-blue-600 to-blue-500", tab: "pipeline" },
          { label: "상품 관리", desc: "재고/가격/상태 일괄 관리", icon: <Package size={20} />, color: "from-emerald-600 to-emerald-500", tab: "products" },
          { label: "회원 관리", desc: "권한 설정 및 관리자 승급", icon: <Users size={20} />, color: "from-violet-600 to-violet-500", tab: "users" },
        ].map((action, idx) => (
          <button
            key={idx}
            onClick={() => {
              window.dispatchEvent(new CustomEvent("admin-tab-change", { detail: action.tab }));
            }}
            className={`group bg-gradient-to-r ${action.color} rounded-2xl p-5 text-left hover:scale-[1.02] active:scale-[0.98] transition-all duration-200 shadow-md`}
          >
            <div className="flex items-center justify-between">
              <div className="w-10 h-10 bg-white/15 rounded-xl flex items-center justify-center text-white backdrop-blur-sm">
                {action.icon}
              </div>
              <ArrowRight size={18} className="text-white/70 group-hover:text-white group-hover:translate-x-1 transition-all" />
            </div>
            <h4 className="text-white font-bold mt-3">{action.label}</h4>
            <p className="text-white/80 text-xs mt-1">{action.desc}</p>
          </button>
        ))}
      </div>

      {/* ═══ 최근 주문 ═══ */}
      <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
        <div className="px-6 py-5 border-b border-slate-200 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center border border-blue-100">
              <Clock size={20} />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">최근 주문</h3>
              <p className="text-xs text-slate-500">가장 최근 결제된 5건의 주문 내역</p>
            </div>
          </div>
        </div>

        {orders.length === 0 ? (
          <div className="p-12 text-center text-slate-400">
            <ShoppingCart size={40} className="mx-auto mb-3 text-slate-300" />
            <p className="font-semibold text-slate-500">아직 주문 내역이 없습니다.</p>
            <p className="text-xs mt-1 text-slate-400">첫 주문이 들어오면 여기에 표시됩니다.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200">
                  <th className="px-6 py-3.5 text-xs font-bold text-slate-500 uppercase tracking-wider">주문번호</th>
                  <th className="px-6 py-3.5 text-xs font-bold text-slate-500 uppercase tracking-wider">주문자</th>
                  <th className="px-6 py-3.5 text-xs font-bold text-slate-500 uppercase tracking-wider">상품</th>
                  <th className="px-6 py-3.5 text-xs font-bold text-slate-500 uppercase tracking-wider">금액</th>
                  <th className="px-6 py-3.5 text-xs font-bold text-slate-500 uppercase tracking-wider">결제</th>
                  <th className="px-6 py-3.5 text-xs font-bold text-slate-500 uppercase tracking-wider">일시</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 bg-white">
                {orders.map((o) => (
                  <tr key={o.id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="px-6 py-4 text-sm font-mono font-bold text-blue-600">{o.order_number}</td>
                    <td className="px-6 py-4 text-sm text-slate-800 font-semibold">{o.customer_name}</td>
                    <td className="px-6 py-4 text-sm text-slate-600 truncate max-w-[200px]">{o.summary_name}</td>
                    <td className="px-6 py-4 text-sm font-extrabold text-slate-900">₩{o.total_amount.toLocaleString()}</td>
                    <td className="px-6 py-4">{statusBadge(o.payment_status)}</td>
                    <td className="px-6 py-4 text-sm text-slate-500">{new Date(o.created_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
