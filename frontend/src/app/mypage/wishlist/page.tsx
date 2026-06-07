"use client";

import { useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import { Loader2, Heart } from "lucide-react";
import Image from "next/image";
import Link from "next/link";

interface WishlistItem {
  id: number;
  product_id: number;
  product_name: string | null;
  product_price: number | null;
  product_image: string | null;
}

export default function WishlistPage() {
  const apiUrl = API_URL;
  const [items, setItems] = useState<WishlistItem[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchWishlist = async () => {
    setLoading(true);
    const token = localStorage.getItem("token");
    if (!token) return;
    try {
      const res = await fetch(`${apiUrl}/api/wishlist/me`, { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) setItems(await res.json());
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchWishlist(); }, []);

  const handleRemove = async (productId: number) => {
    const token = localStorage.getItem("token");
    await fetch(`${apiUrl}/api/wishlist/toggle`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ product_id: productId }),
    });
    fetchWishlist();
  };

  if (loading) return <div className="py-20 flex justify-center"><Loader2 className="animate-spin text-slate-400" size={32} /></div>;

  return (
    <div className="bg-white dark:bg-slate-800 rounded-3xl shadow-sm border border-slate-200/60 dark:border-slate-700 p-8 sm:p-10">
      <div className="mb-8 pb-6 border-b border-slate-100 dark:border-slate-700">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-3"><Heart className="text-rose-500" size={28} /> Wishlist</h1>
        <p className="text-sm text-slate-500 mt-2">찜한 상품 목록입니다. ({items.length}개)</p>
      </div>

      {items.length === 0 ? (
        <div className="py-20 text-center bg-slate-50 dark:bg-slate-900/40 rounded-2xl border border-dashed border-slate-300 dark:border-slate-700">
          <Heart size={32} className="mx-auto mb-4 text-slate-400" />
          <h3 className="text-lg font-bold text-slate-700 dark:text-slate-300">찜한 상품이 없습니다</h3>
          <p className="text-slate-500 mt-2 text-sm">마음에 드는 상품의 하트를 눌러 담아보세요.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {items.map(item => (
            <div key={item.id} className="bg-white dark:bg-slate-800 rounded-2xl border border-slate-200 dark:border-slate-700 overflow-hidden group">
              <Link href={`/product/${item.product_id}`} className="block relative aspect-square bg-slate-100 dark:bg-slate-700">
                {item.product_image ? (
                  <Image src={`${apiUrl}${item.product_image}`} alt={item.product_name || ""} fill className="object-cover group-hover:scale-105 transition-transform" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-sm text-slate-400 font-bold">LUXAI</div>
                )}
              </Link>
              <div className="p-4">
                <Link href={`/product/${item.product_id}`} className="font-bold text-slate-900 dark:text-white hover:text-blue-600 transition line-clamp-1">{item.product_name}</Link>
                <p className="text-blue-600 font-extrabold mt-1">₩{(item.product_price || 0).toLocaleString()}</p>
                <button onClick={() => handleRemove(item.product_id)} className="mt-3 text-xs text-slate-400 hover:text-red-500 font-bold transition">찜 해제</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}