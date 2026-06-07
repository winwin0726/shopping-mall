"use client";

import { motion, AnimatePresence } from "framer-motion";
import { X, CreditCard, Wallet, Landmark, CheckCircle, Loader2, MapPin } from "lucide-react";
import { useState, useEffect } from "react";
import Image from "next/image";
import { useAuth } from "@/hooks/useAuth";
import { API_URL, authFetch } from "@/lib/api";

interface CheckoutModalProps {
  isOpen: boolean;
  onClose: () => void;
  product?: any;
  quantity?: number;
  cartItems?: any[];
  totalAmount: number;
  onComplete: (orderNumber: string) => void;
}

export default function CheckoutModal({ isOpen, onClose, product, quantity, cartItems, totalAmount, onComplete }: CheckoutModalProps) {
  const { user } = useAuth();
  const [method, setMethod] = useState<"card" | "kakaopay" | "bank">("card");
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [orderNumberState, setOrderNumberState] = useState("");
  const [address, setAddress] = useState<any>(null);
  const [coupons, setCoupons] = useState<any[]>([]);
  const [selectedCouponId, setSelectedCouponId] = useState<number | null>(null);
  const [pointsInput, setPointsInput] = useState<number>(0);

  useEffect(() => {
    if (isOpen && user) {
      // 기본 배송지
      authFetch(`${API_URL}/api/address/me/default`)
        .then(res => res.ok ? res.json() : null)
        .then(data => { if (data) setAddress(data); })
        .catch(() => {});
      // 사용 가능한 쿠폰 목록
      authFetch(`${API_URL}/api/auth/me/coupons`)
        .then(res => res.ok ? res.json() : [])
        .then(data => setCoupons(Array.isArray(data) ? data : []))
        .catch(() => setCoupons([]));
    }
    if (!isOpen) {
      // 모달이 닫히면 선택 초기화
      setSelectedCouponId(null);
      setPointsInput(0);
    }
  }, [isOpen, user]);

  if (!isOpen) return null;

  // 할인 계산 (서버가 최종 재검증하지만 UI 표시·전송용으로 동일 규칙 적용)
  const selectedCoupon = coupons.find((c) => c.id === selectedCouponId) || null;
  const couponDiscount = selectedCoupon ? Math.min(selectedCoupon.discount_amount, totalAmount) : 0;
  const remainingAfterCoupon = totalAmount - couponDiscount;
  const maxUsablePoints = Math.max(0, Math.min(user?.reward_points || 0, remainingAfterCoupon));
  const pointsToUse = Math.max(0, Math.min(Math.floor(pointsInput || 0), maxUsablePoints));
  const finalAmount = Math.max(0, remainingAfterCoupon - pointsToUse);

  const handleCheckout = async () => {
    setIsProcessing(true);
    await new Promise(r => setTimeout(r, 2000));
    const orderNumber = `AV-${Date.now().toString().slice(-6)}-${Math.floor(Math.random() * 1000)}`;
    setOrderNumberState(orderNumber);

    try {
      let apiEndpoint = `${API_URL}/api/orders/orders`;
      let payload: any = {
        customer_name: address ? address.recipient_name : (user ? user.name : "Guest"),
        customer_phone: address ? address.phone : "010-0000-0000",
        total_amount: finalAmount,
        payment_method: method.toUpperCase(),
        payment_id: "tx_" + Date.now(),
        shipping_postal_code: address?.postal_code || null,
        shipping_address: address?.address_line1 || null,
        shipping_address_detail: address?.address_line2 || null,
        coupon_id: selectedCouponId,
        used_points: pointsToUse,
      };

      if (cartItems && cartItems.length > 0) {
        apiEndpoint = `${API_URL}/api/orders/checkout/cart`;
        payload.cart_item_ids = cartItems.map((item: any) => item.id);
      } else if (product) {
        payload.user_id = user ? (user as any).id : null;
        payload.order_number = orderNumber;
        payload.payment_status = method === "bank" ? "PENDING" : "PAID";
        payload.items = [{ product_id: product.id, quantity: quantity || 1, unit_price: product.sale_price || product.base_price }];
      }

      const res = await authFetch(apiEndpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        const data = await res.json();
        if (data.order_number) setOrderNumberState(data.order_number);
        setIsSuccess(true);
        setTimeout(() => onComplete(data.order_number || orderNumber), 1500);
      } else {
        throw new Error("결제 실패");
      }
    } catch {
      alert("결제 처리 중 오류가 발생했습니다.");
      setIsProcessing(false);
    }
  };

  const isCartMode = cartItems && cartItems.length > 0;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={!isProcessing ? onClose : undefined} className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" />
        <motion.div initial={{ scale: 0.95, opacity: 0, y: 20 }} animate={{ scale: 1, opacity: 1, y: 0 }} exit={{ scale: 0.95, opacity: 0, y: 20 }} className="relative w-full max-w-xl bg-white dark:bg-slate-900 rounded-3xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
          {isSuccess ? (
            <div className="flex flex-col items-center justify-center p-12 text-center min-h-[400px]">
              <motion.div initial={{ scale: 0.5, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="w-24 h-24 bg-green-100 text-green-500 rounded-full flex items-center justify-center mb-6"><CheckCircle size={48} /></motion.div>
              <h2 className="text-2xl font-black text-slate-900 dark:text-white mb-2">결제가 완료되었습니다!</h2>
              <p className="text-slate-500 mb-6 font-medium">주문번호: {orderNumberState}</p>
              <Loader2 className="animate-spin text-slate-300" size={24} />
            </div>
          ) : (
            <>
              <div className="px-6 py-5 border-b border-slate-100 dark:border-slate-800 flex justify-between items-center">
                <h2 className="text-lg font-bold text-slate-900 dark:text-white">🚀 주문 / 결제</h2>
                <button onClick={onClose} disabled={isProcessing} className="p-2 text-slate-400 hover:text-slate-600 transition rounded-full bg-slate-50 dark:bg-slate-800"><X size={20} /></button>
              </div>
              <div className="p-6 overflow-y-auto">
                {/* 배송지 */}
                <h3 className="text-sm font-bold text-slate-500 uppercase tracking-widest mb-3">배송지 정보</h3>
                <div className="bg-blue-50/50 dark:bg-slate-800 p-4 rounded-2xl border border-blue-100 dark:border-slate-700 mb-6">
                  {address ? (
                    <div className="flex items-start gap-3">
                      <MapPin size={20} className="text-blue-500 mt-0.5 shrink-0" />
                      <div>
                        <p className="text-slate-900 dark:text-white font-bold">{address.recipient_name} <span className="text-slate-500 text-sm ml-2 font-normal">{address.phone}</span></p>
                        <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">[{address.postal_code}] {address.address_line1} {address.address_line2}</p>
                      </div>
                    </div>
                  ) : (
                    <p className="text-sm text-slate-500">기본 배송지를 등록해두면 빠른 결제가 가능합니다.</p>
                  )}
                </div>
                {/* 결제수단 */}
                <h3 className="text-sm font-bold text-slate-500 uppercase tracking-widest mb-4">결제 수단</h3>
                <div className="grid grid-cols-3 gap-3 mb-8">
                  {([["card", "신용카드", CreditCard, "blue"], ["kakaopay", "카카오페이", Wallet, "yellow"], ["bank", "무통장", Landmark, "emerald"]] as const).map(([key, label, Icon, color]) => (
                    <button key={key} onClick={() => setMethod(key as any)} className={`p-4 rounded-xl border-2 flex flex-col items-center justify-center gap-2 transition-all ${method === key ? `border-${color}-600 bg-${color}-50 dark:bg-${color}-900/20 shadow-md` : "border-slate-200 dark:border-slate-700 text-slate-500"}`}>
                      <Icon size={24} />
                      <span className="text-xs font-bold">{label}</span>
                    </button>
                  ))}
                </div>

                {/* 할인 적용 (쿠폰 / 적립금) — 로그인 사용자 전용 */}
                {user && (
                  <>
                    <h3 className="text-sm font-bold text-slate-500 uppercase tracking-widest mb-4">할인 적용</h3>
                    <div className="space-y-3 mb-2">
                      {/* 쿠폰 선택 */}
                      <div className="flex items-center justify-between gap-3">
                        <label className="text-sm font-semibold text-slate-600 dark:text-slate-300 shrink-0">쿠폰</label>
                        <select
                          value={selectedCouponId ?? ""}
                          onChange={(e) => setSelectedCouponId(e.target.value ? Number(e.target.value) : null)}
                          className="flex-1 max-w-[62%] px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm font-medium text-slate-800 dark:text-slate-100"
                        >
                          <option value="">{coupons.length ? "쿠폰 선택 안함" : "보유 쿠폰 없음"}</option>
                          {coupons.map((c) => (
                            <option key={c.id} value={c.id}>
                              {c.name} (₩{Number(c.discount_amount).toLocaleString()})
                            </option>
                          ))}
                        </select>
                      </div>
                      {/* 적립금 사용 */}
                      <div className="flex items-center justify-between gap-3">
                        <label className="text-sm font-semibold text-slate-600 dark:text-slate-300 shrink-0">
                          적립금 <span className="text-xs text-slate-400">(보유 {(user.reward_points || 0).toLocaleString()}P)</span>
                        </label>
                        <div className="flex items-center gap-2 flex-1 max-w-[62%]">
                          <input
                            type="number"
                            min={0}
                            max={maxUsablePoints}
                            value={pointsInput || ""}
                            onChange={(e) => setPointsInput(Number(e.target.value) || 0)}
                            placeholder="0"
                            className="flex-1 w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm font-medium text-right text-slate-800 dark:text-slate-100"
                          />
                          <button
                            type="button"
                            onClick={() => setPointsInput(maxUsablePoints)}
                            className="px-3 py-2 rounded-xl bg-slate-100 dark:bg-slate-700 text-xs font-bold text-slate-600 dark:text-slate-200 shrink-0 hover:bg-slate-200 transition"
                          >
                            최대
                          </button>
                        </div>
                      </div>
                    </div>
                  </>
                )}
              </div>
              <div className="p-6 border-t border-slate-100 dark:border-slate-800 flex flex-col sm:flex-row justify-between items-center gap-4">
                <div className="text-center sm:text-left">
                  {(couponDiscount > 0 || pointsToUse > 0) && (
                    <div className="text-xs text-slate-400 mb-1 space-y-0.5">
                      <p>상품 금액 <span className="font-semibold text-slate-500 dark:text-slate-300">₩{totalAmount.toLocaleString()}</span></p>
                      {couponDiscount > 0 && <p>쿠폰 할인 <span className="font-semibold text-rose-500">-₩{couponDiscount.toLocaleString()}</span></p>}
                      {pointsToUse > 0 && <p>적립금 사용 <span className="font-semibold text-rose-500">-₩{pointsToUse.toLocaleString()}</span></p>}
                    </div>
                  )}
                  <p className="text-slate-500 text-sm font-semibold">최종 결제 금액</p>
                  <p className="text-3xl font-black text-slate-900 dark:text-white">₩{finalAmount.toLocaleString()}</p>
                </div>
                <button onClick={handleCheckout} disabled={isProcessing} className="w-full sm:w-auto px-10 py-4 bg-slate-900 dark:bg-blue-600 text-white font-extrabold rounded-2xl flex items-center justify-center transition-all hover:bg-black shadow-xl disabled:opacity-70">
                  {isProcessing ? <><Loader2 className="animate-spin mr-2" size={20} /> 진행중...</> : "결제 완료하기"}
                </button>
              </div>
            </>
          )}
        </motion.div>
      </div>
    </AnimatePresence>
  );
}