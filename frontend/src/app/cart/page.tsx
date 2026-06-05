"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { ShoppingBag, Loader2, Minus, Plus, Trash2, ArrowRight } from "lucide-react";
import CheckoutModal from "@/components/CheckoutModal";

interface CartItem {
  id: number;
  product_id: number;
  quantity: number;
  product_name: string;
  product_price: number;
  product_image: string | null;
}

export default function CartPage() {
  const router = useRouter();
  const [items, setItems] = useState<CartItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [isCheckoutOpen, setIsCheckoutOpen] = useState(false);

  const fetchCartItems = async () => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login?redirect=/cart");
      return;
    }
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/api/cart/me`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setItems(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCartItems();
  }, [router]);

  const handleUpdateQuantity = async (itemId: number, newQuantity: number) => {
      if (newQuantity <= 0) {
          handleRemoveItem(itemId);
          return;
      }
      setItems(prev => prev.map(i => i.id === itemId ? {...i, quantity: newQuantity} : i));
      
      const token = localStorage.getItem("token");
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      try {
        await fetch(`${apiUrl}/api/cart/items/${itemId}`, {
           method: "PUT",
           headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
           body: JSON.stringify({ quantity: newQuantity })
        });
      } catch (e) {
         fetchCartItems();
      }
  };

  const handleRemoveItem = async (itemId: number) => {
      setItems(prev => prev.filter(i => i.id !== itemId));
      const token = localStorage.getItem("token");
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      try {
        await fetch(`${apiUrl}/api/cart/items/${itemId}`, {
           method: "DELETE",
           headers: { Authorization: `Bearer ${token}` }
        });
      } catch(e) {
          fetchCartItems();
      }
  };

  const totalAmount = items.reduce((acc, item) => acc + (item.product_price * item.quantity), 0);

  if (loading) {
    return <div className="min-h-screen flex items-center justify-center bg-slate-50"><Loader2 className="animate-spin text-slate-400" size={32} /></div>;
  }

  return (
    <div className="min-h-screen pt-24 pb-16 bg-slate-50 dark:bg-slate-900">
      <div className="max-w-[1200px] mx-auto px-4 sm:px-6">
        <h1 className="text-3xl font-black text-slate-900 dark:text-white mb-8 flex items-center gap-3">
          <ShoppingBag className="text-blue-600" size={32} />
          Shopping Cart
        </h1>

        {items.length === 0 ? (
          <div className="bg-white dark:bg-slate-800 rounded-3xl p-16 text-center shadow-sm border border-slate-200/60 dark:border-slate-700">
             <div className="w-20 h-20 bg-slate-100 dark:bg-slate-700 rounded-full flex items-center justify-center mx-auto mb-6">
                 <ShoppingBag size={32} className="text-slate-400" />
             </div>
             <h2 className="text-2xl font-bold text-slate-800 dark:text-white mb-3">장바구니가 비어있습니다</h2>
             <p className="text-slate-500 mb-8">마음에 드는 상품을 장바구니에 담아보세요.</p>
             <Link href="/" className="inline-flex px-8 py-3.5 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl transition">
                쇼핑 계속하기
             </Link>
          </div>
        ) : (
          <div className="flex flex-col lg:flex-row gap-8">
            {/* Cart Items List */}
            <div className="flex-1 space-y-4">
               {items.map(item => (
                 <div key={item.id} className="bg-white dark:bg-slate-800 rounded-2xl p-4 sm:p-6 shadow-sm border border-slate-200/60 dark:border-slate-700 flex flex-col sm:flex-row items-center gap-6 relative">
                    <button onClick={() => handleRemoveItem(item.id)} className="absolute top-4 right-4 text-slate-400 hover:text-red-500 transition">
                       <Trash2 size={20} />
                    </button>
                    <Link href={`/product/${item.product_id}`} className="w-24 h-24 sm:w-32 sm:h-32 bg-slate-100 dark:bg-slate-700 rounded-xl overflow-hidden relative flex-shrink-0 cursor-pointer border border-slate-200 dark:border-slate-600">
                       {item.product_image ? (
                           <img 
                             src={item.product_image.startsWith("http") ? item.product_image : `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}${item.product_image}`} 
                             alt={item.product_name} 
                             className="w-full h-full object-cover hover:scale-105 transition-transform" 
                           />
                       ) : (
                           <div className="w-full h-full flex items-center justify-center text-xs text-slate-400 font-bold">IMAGE</div>
                       )}
                    </Link>
                    <div className="flex-1 w-full flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                       <div>
                          <Link href={`/product/${item.product_id}`} className="text-lg font-bold text-slate-900 dark:text-white hover:text-blue-600 transition line-clamp-2">
                              {item.product_name}
                          </Link>
                          <p className="text-slate-500 font-medium mt-1">{item.product_price.toLocaleString()}원</p>
                       </div>
                       
                       <div className="flex items-center gap-6 w-full sm:w-auto justify-between sm:justify-end">
                          <div className="flex items-center border border-slate-200 dark:border-slate-600 rounded-lg overflow-hidden shrink-0">
                             <button onClick={() => handleUpdateQuantity(item.id, item.quantity - 1)} className="w-9 h-9 flex items-center justify-center bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 transition"><Minus size={14}/></button>
                             <span className="w-10 text-center font-bold text-sm bg-white dark:bg-slate-800">{item.quantity}</span>
                             <button onClick={() => handleUpdateQuantity(item.id, item.quantity + 1)} className="w-9 h-9 flex items-center justify-center bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 transition"><Plus size={14}/></button>
                          </div>
                          <div className="text-right">
                              <p className="text-lg font-black text-slate-900 dark:text-white">{(item.product_price * item.quantity).toLocaleString()}원</p>
                          </div>
                       </div>
                    </div>
                 </div>
               ))}
            </div>

            {/* Order Summary Checkout Panel */}
            <div className="w-full lg:w-96 flex-shrink-0">
               <div className="bg-white dark:bg-slate-800 rounded-2xl p-6 sm:p-8 shadow-sm border border-slate-200/60 dark:border-slate-700 sticky top-28">
                  <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-6">주문 요약</h2>
                  
                  <div className="space-y-4 mb-6 text-sm font-medium">
                     <div className="flex justify-between text-slate-500">
                        <span>상품 금액 ({items.length}건)</span>
                        <span className="text-slate-900 dark:text-white">{totalAmount.toLocaleString()}원</span>
                     </div>
                     <div className="flex justify-between text-slate-500">
                        <span>배송비</span>
                        <span className="text-slate-900 dark:text-white">무료</span>
                     </div>
                     <div className="flex justify-between text-slate-500">
                        <span>할인 금액</span>
                        <span className="text-red-500">-0원</span>
                     </div>
                  </div>

                  <div className="pt-6 border-t border-slate-200 dark:border-slate-700 mb-8">
                     <div className="flex justify-between items-end">
                        <span className="text-base font-bold text-slate-900 dark:text-white">최종 결제 금액</span>
                        <span className="text-3xl font-black text-blue-600 dark:text-blue-400">{totalAmount.toLocaleString()}원</span>
                     </div>
                  </div>

                  <button onClick={() => setIsCheckoutOpen(true)} className="w-full py-4 bg-slate-900 hover:bg-black dark:bg-blue-600 dark:hover:bg-blue-500 text-white text-lg font-bold rounded-xl flex items-center justify-center gap-2 transition-all shadow-lg active:scale-95">
                     <span>결제 진행하기</span>
                     <ArrowRight size={20} />
                  </button>
                  <p className="text-xs text-center text-slate-500 mt-4">결제 시 배송비가 무료로 적용됩니다.</p>
               </div>
            </div>
          </div>
        )}
      </div>

      {isCheckoutOpen && (
        <CheckoutModal 
          isOpen={isCheckoutOpen} 
          onClose={() => setIsCheckoutOpen(false)}
          cartItems={items}
          totalAmount={totalAmount}
          onComplete={(orderNumber) => {
            setIsCheckoutOpen(false);
            setItems([]);
            router.push("/mypage/orders");
          }}
        />
      )}
    </div>
  );
}
