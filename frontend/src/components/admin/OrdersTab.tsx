"use client";
import { authFetch, API_URL } from "@/lib/api";

import { useEffect, useState, useCallback } from "react";
import {
  CreditCard, Search, Loader2, AlertCircle, RefreshCw,
  ChevronLeft, ChevronRight, Filter, ChevronDown, Package
} from "lucide-react";

interface OrderItem {
  product_id: number;
  product_name: string;
  quantity: number;
  unit_price: number;
}

interface Order {
  id: number;
  order_number: string;
  customer_name: string;
  customer_phone: string | null;
  total_amount: number;
  payment_method: string;
  payment_status: string;
  payment_id: string | null;
  created_at: string;
  summary_name: string;
  items: OrderItem[];
}

export default function OrdersTab() {
  const apiUrl = API_URL;
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const perPage = 12;

  const fetchOrders = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      let url = `${apiUrl}/api/orders/admin/orders?`;
      if (statusFilter) url += `status=${statusFilter}&`;
      if (searchTerm) url += `search=${encodeURIComponent(searchTerm)}&`;

      const res = await authFetch(url);
      if (!res.ok) throw new Error("주문 목록을 불러올 수 없습니다.");
      const data = await res.json();
      setOrders(data);
      setPage(1);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, searchTerm]);

  useEffect(() => {
    fetchOrders();
  }, [fetchOrders]);

  const handleStatusChange = async (orderId: number, newStatus: string) => {
    try {
      const res = await authFetch(`${apiUrl}/api/orders/admin/orders/${orderId}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus }),
      });
      if (!res.ok) throw new Error("상태 변경 실패");
      fetchOrders();
    } catch (err: any) {
      alert(err.message);
    }
  };

  // 페이지네이션
  const totalPages = Math.ceil(orders.length / perPage);
  const paged = orders.slice((page - 1) * perPage, page * perPage);

  const statusBadge = (status: string) => {
    const map: Record<string, { bg: string; text: string; label: string }> = {
      PAID: { bg: "bg-emerald-500/15 border-emerald-500/30", text: "text-emerald-400", label: "결제완료" },
      PENDING: { bg: "bg-yellow-500/15 border-yellow-500/30", text: "text-yellow-400", label: "대기중" },
      CANCELLED: { bg: "bg-red-500/15 border-red-500/30", text: "text-red-400", label: "취소" },
    };
    const s = map[status] || { bg: "bg-slate-700 border-slate-600", text: "text-slate-300", label: status };
    return (
      <span className={`px-2.5 py-1 rounded-full text-xs font-bold border ${s.bg} ${s.text}`}>
        {s.label}
      </span>
    );
  };

  const paymentMethodLabel = (method: string) => {
    const map: Record<string, string> = {
      EASY_PAY: "간편결제",
      CARD: "카드",
      BANK_TRANSFER: "계좌이체",
      VIRTUAL: "가상결제",
    };
    return map[method] || method;
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* 헤더 */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-white mb-1 tracking-tight">결제 및 주문 현황</h2>
          <p className="text-slate-400 text-sm">
            총 <span className="text-white font-bold">{orders.length}</span>건의 주문을 관리합니다.
          </p>
        </div>
        <button
          onClick={fetchOrders}
          className="bg-slate-800 hover:bg-slate-700 text-white px-5 py-2.5 rounded-lg flex items-center transition-colors shadow-lg font-medium shrink-0"
        >
          <RefreshCw size={16} className={`mr-2 ${loading ? "animate-spin text-blue-400" : ""}`} /> 새로고침
        </button>
      </div>

      {/* 필터 바 */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            placeholder="주문번호 또는 주문자명 검색..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && fetchOrders()}
            className="w-full bg-slate-900 border border-slate-700 rounded-xl pl-10 pr-4 py-2.5 text-white text-sm placeholder:text-slate-500 focus:outline-none focus:border-blue-500 transition"
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter size={16} className="text-slate-500" />
          {[
            { value: "", label: "전체" },
            { value: "PAID", label: "결제완료" },
            { value: "PENDING", label: "대기" },
            { value: "CANCELLED", label: "취소" },
          ].map((s) => (
            <button
              key={s.value}
              onClick={() => setStatusFilter(s.value)}
              className={`px-3 py-2 rounded-lg text-xs font-bold transition ${
                statusFilter === s.value
                  ? "bg-blue-600 text-white shadow-lg shadow-blue-900/30"
                  : "bg-slate-800 text-slate-400 hover:text-white hover:bg-slate-700"
              }`}
            >
              {s.label}
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
                <th className="px-5 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider w-8"></th>
                <th className="px-5 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">주문번호</th>
                <th className="px-5 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">주문자</th>
                <th className="px-5 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">상품</th>
                <th className="px-5 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">결제금액</th>
                <th className="px-5 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">결제방법</th>
                <th className="px-5 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">상태</th>
                <th className="px-5 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">일시</th>
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
                    <CreditCard size={40} className="mx-auto mb-3 text-slate-700" />
                    주문 내역이 없습니다.
                  </td>
                </tr>
              ) : (
                paged.map((o) => (
                  <>
                    <tr
                      key={o.id}
                      className="hover:bg-slate-800/40 transition-colors cursor-pointer"
                      onClick={() => setExpandedId(expandedId === o.id ? null : o.id)}
                    >
                      <td className="px-5 py-3">
                        <ChevronDown
                          size={16}
                          className={`text-slate-500 transition-transform ${expandedId === o.id ? "rotate-180" : ""}`}
                        />
                      </td>
                      <td className="px-5 py-3 text-sm font-mono text-blue-400">{o.order_number}</td>
                      <td className="px-5 py-3">
                        <p className="text-sm font-medium text-white">{o.customer_name}</p>
                        {o.customer_phone && (
                          <p className="text-xs text-slate-500">{o.customer_phone}</p>
                        )}
                      </td>
                      <td className="px-5 py-3 text-sm text-slate-300 truncate max-w-[180px]">{o.summary_name}</td>
                      <td className="px-5 py-3 text-sm font-bold text-white">₩{o.total_amount.toLocaleString()}</td>
                      <td className="px-5 py-3 text-sm text-slate-400">{paymentMethodLabel(o.payment_method)}</td>
                      <td className="px-5 py-3">{statusBadge(o.payment_status)}</td>
                      <td className="px-5 py-3 text-sm text-slate-500">{new Date(o.created_at).toLocaleDateString()}</td>
                      <td className="px-5 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                        <select
                          value={o.payment_status}
                          onChange={(e) => handleStatusChange(o.id, e.target.value)}
                          className="bg-slate-800 border border-slate-700 rounded-lg px-2 py-1 text-xs text-white focus:outline-none focus:border-blue-500 transition"
                        >
                          <option value="PAID">결제완료</option>
                          <option value="PENDING">대기</option>
                          <option value="CANCELLED">취소</option>
                        </select>
                      </td>
                    </tr>

                    {/* 확장: 주문 아이템 상세 */}
                    {expandedId === o.id && (
                      <tr key={`${o.id}-detail`}>
                        <td colSpan={9} className="bg-slate-950 px-8 py-5">
                          <div className="flex items-center gap-2 mb-3">
                            <Package size={16} className="text-blue-400" />
                            <span className="text-sm font-bold text-white">주문 상품 내역</span>
                          </div>
                          {o.items.length === 0 ? (
                            <p className="text-sm text-slate-500 italic">상품 데이터 없음</p>
                          ) : (
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                              {o.items.map((item, idx) => (
                                <div
                                  key={idx}
                                  className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex items-center gap-3"
                                >
                                  <div className="w-10 h-10 rounded-lg bg-slate-800 flex items-center justify-center text-slate-600 text-xs shrink-0">
                                    #{item.product_id}
                                  </div>
                                  <div className="flex-1 min-w-0">
                                    <p className="text-sm font-medium text-white truncate">{item.product_name}</p>
                                    <p className="text-xs text-slate-500">
                                      {item.quantity}개 × ₩{item.unit_price.toLocaleString()}
                                    </p>
                                  </div>
                                  <p className="text-sm font-bold text-emerald-400 shrink-0">
                                    ₩{(item.quantity * item.unit_price).toLocaleString()}
                                  </p>
                                </div>
                              ))}
                            </div>
                          )}
                        </td>
                      </tr>
                    )}
                  </>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* 페이지네이션 */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-6 py-4 border-t border-slate-800">
            <p className="text-sm text-slate-500">
              {orders.length}건 중 {(page - 1) * perPage + 1}–{Math.min(page * perPage, orders.length)}
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
    </div>
  );
}
