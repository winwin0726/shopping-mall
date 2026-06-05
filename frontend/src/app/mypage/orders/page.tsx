"use client";

import { useEffect, useState } from "react";
import { Package, Clock, CreditCard, Loader2, Truck, Copy } from "lucide-react";
import Image from "next/image";

interface OrderItem {
  product_id: number;
  product_name: string;
  quantity: number;
  unit_price: number;
  image_url: string | null;
}

interface Order {
  id: number;
  order_number: string;
  total_amount: number;
  payment_status: string;
  created_at: string;
  summary_name: string;
  shipping_status?: string;
  tracking_number?: string;
  items: OrderItem[];
}

export default function OrdersPage() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchOrders = async () => {
      const token = localStorage.getItem("token");
      try {
        const res = await fetch(`${apiUrl}/api/orders/me/orders`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (res.ok) {
          const data = await res.json();
          setOrders(data);
        }
      } catch (err) {
        console.error("Failed to fetch orders", err);
      } finally {
        setLoading(false);
      }
    };
    fetchOrders();
  }, []);

  if (loading) {
    return <div className="py-20 flex justify-center"><Loader2 className="animate-spin text-slate-400" size={32} /></div>;
  }

  return (
    <div className="bg-white dark:bg-slate-800 rounded-3xl shadow-sm border border-slate-200/60 dark:border-slate-700/50 overflow-hidden">
      <div className="p-8 sm:p-10">
        <div className="flex items-center space-x-3 mb-8 pb-6 border-b border-slate-100 dark:border-slate-700">
          <div className="bg-indigo-100 dark:bg-indigo-900/40 p-2.5 rounded-lg text-indigo-600 dark:text-indigo-400">
            <Package size={24} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Order History</h1>
            <p className="text-sm text-slate-500 mt-1">주문 내역과 배송 상태를 확인하실 수 있습니다.</p>
          </div>
        </div>

        {orders.length === 0 ? (
          <div className="py-24 text-center border-2 border-dashed border-slate-200 dark:border-slate-700 rounded-2xl bg-slate-50/50 dark:bg-slate-900/20">
            <div className="mx-auto w-16 h-16 bg-slate-100 dark:bg-slate-800 rounded-full flex items-center justify-center mb-4 text-slate-400">
              <Package size={32} />
            </div>
            <h3 className="text-lg font-bold text-slate-700 dark:text-slate-300">최근 1개월 내 주문 내역이 없습니다.</h3>
            <p className="text-slate-500 mt-2 text-sm">LUXAI AI 스타일 스튜디오를 통해 나만의 아이템을 찾아보세요.</p>
          </div>
        ) : (
          <div className="space-y-6">
            {orders.map((order) => (
              <div key={order.id} className="border border-slate-200 dark:border-slate-700 rounded-2xl p-6 bg-white dark:bg-slate-800/50 hover:shadow-lg transition-all duration-300">
                
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-5 pb-4 border-b border-slate-100 dark:border-slate-700/50 gap-4 sm:gap-0">
                  <div className="flex items-center space-x-4">
                    <span className="text-xs font-black text-slate-900 dark:text-white bg-slate-100 dark:bg-slate-700 px-3 py-1 rounded-md tracking-wider">
                      #{order.order_number}
                    </span>
                    <div className="text-sm font-medium text-slate-500 flex items-center">
                      <Clock size={14} className="mr-1.5" />
                      {new Date(order.created_at).toLocaleDateString()}
                    </div>
                  </div>
                  <div className="flex items-center space-x-3">
                    {/* 배송 상태 표시 */}
                    {order.shipping_status && (
                        <div className={`px-3 py-1 flex items-center text-xs font-bold rounded-full border ${order.shipping_status === 'SHIPPING' ? 'bg-blue-50 border-blue-200 text-blue-700 dark:bg-blue-900/20 dark:border-blue-800/50 dark:text-blue-400' : 'bg-slate-100 border-slate-200 text-slate-600 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-400'}`}>
                           <Truck size={12} className="mr-1" />
                           {order.shipping_status === 'PREPARING' ? '상품준비중' : order.shipping_status === 'SHIPPING' ? '배송중' : '배송완료'}
                        </div>
                    )}
                    {order.tracking_number && (
                        <div className="px-3 py-1 flex items-center text-xs font-bold rounded-full border bg-slate-50 border-slate-200 text-slate-500 dark:bg-slate-800 dark:border-slate-700 cursor-pointer hover:bg-slate-100 transition-colors" onClick={() => { navigator.clipboard.writeText(order.tracking_number!); alert("운송장 번호가 복사되었습니다."); }}>
                           송장: {order.tracking_number} <Copy size={12} className="ml-1" />
                        </div>
                    )}
                    
                    {/* 결제 상태 표시 */}
                    <div className={`px-4 py-1.5 text-xs font-bold rounded-full border ${order.payment_status === 'PAID' ? 'bg-green-50/50 border-green-200 text-green-700 dark:bg-green-900/20 dark:border-green-800/50 dark:text-green-400' : 'bg-amber-50/50 border-amber-200 text-amber-700 dark:bg-amber-900/20 dark:border-amber-800/50 dark:text-amber-400'}`}>
                      {order.payment_status === 'PAID' ? '결제완료' : '결제대기'}
                    </div>
                  </div>
                </div>

                <div className="space-y-4">
                  {order.items.map((item, idx) => (
                    <div key={idx} className="flex items-center space-x-5 group p-2 hover:bg-slate-50 dark:hover:bg-slate-700/20 rounded-xl transition-colors">
                      <div className="w-20 h-20 bg-slate-100 dark:bg-slate-700 rounded-xl relative overflow-hidden flex-shrink-0 border border-slate-200/50 dark:border-slate-600">
                        {item.image_url ? (
                          <Image src={`${apiUrl}${item.image_url}`} alt={item.product_name} fill className="object-cover group-hover:scale-105 transition-transform duration-500" />
                        ) : (
                          <div className="absolute inset-0 flex items-center justify-center text-xs font-bold text-slate-400">LUXAI</div>
                        )}
                      </div>
                      <div className="flex-1">
                        <p className="text-base font-bold text-slate-900 dark:text-white leading-tight mb-1">{item.product_name}</p>
                        <p className="text-sm text-slate-500 font-medium">수량: {item.quantity} 개 / 단가 ₩{item.unit_price.toLocaleString()}</p>
                      </div>
                      <div className="text-right hidden sm:block">
                        <p className="font-extrabold text-slate-900 dark:text-white">₩{(item.quantity * item.unit_price).toLocaleString()}</p>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="mt-6 pt-5 flex justify-between items-center border-t border-slate-100 dark:border-slate-700/50">
                  <div className="text-sm font-bold text-slate-500 uppercase tracking-widest">Total Amount</div>
                  <div className="flex items-center text-2xl font-black text-indigo-600 dark:text-indigo-400">
                    <CreditCard size={20} className="mr-2" />
                    ₩{order.total_amount.toLocaleString()}
                  </div>
                </div>

              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
