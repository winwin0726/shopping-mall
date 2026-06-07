"use client";

import { useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import { Edit3, Star, Trash2, Loader2, PackageOpen } from "lucide-react";
import Image from "next/image";
import Link from "next/link";

interface ReviewItem {
  id: number;
  product_id: number;
  rating: number;
  content: string | null;
  created_at: string;
  product_name: string | null;
  product_image: string | null;
}

export default function MyReviewsPage() {
  const apiUrl = API_URL;
  const [reviews, setReviews] = useState<ReviewItem[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchReviews = async () => {
    setLoading(true);
    const token = localStorage.getItem("token");
    if (!token) return;
    try {
      const res = await fetch(`${apiUrl}/api/reviews/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setReviews(await res.json());
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReviews();
  }, []);

  const handleDelete = async (id: number) => {
    if (!confirm("이 리뷰를 삭제하시겠습니까?")) return;
    const token = localStorage.getItem("token");
    try {
      const res = await fetch(`${apiUrl}/api/reviews/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) fetchReviews();
    } catch (err) {
      console.error(err);
    }
  };

  const renderStars = (rating: number) => (
    <div className="flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((s) => (
        <Star
          key={s}
          size={16}
          className={
            s <= rating
              ? "text-amber-400 fill-amber-400"
              : "text-slate-300 dark:text-slate-600"
          }
        />
      ))}
    </div>
  );

  if (loading)
    return (
      <div className="py-20 flex justify-center">
        <Loader2 className="animate-spin text-slate-400" size={32} />
      </div>
    );

  return (
    <div className="bg-white dark:bg-slate-800 rounded-3xl shadow-sm border border-slate-200/60 dark:border-slate-700 p-8 sm:p-10">
      {/* Header */}
      <div className="flex items-center justify-between mb-8 pb-6 border-b border-slate-100 dark:border-slate-700">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-3">
            <Edit3 className="text-blue-600" size={28} /> My Reviews
          </h1>
          <p className="text-sm text-slate-500 mt-2">
            내가 작성한 상품 리뷰를 확인하고 관리하세요.
          </p>
        </div>
        <span className="text-sm font-bold text-slate-400">
          총 {reviews.length}건
        </span>
      </div>

      {/* Empty State */}
      {reviews.length === 0 ? (
        <div className="py-20 text-center bg-slate-50 dark:bg-slate-900/40 rounded-2xl border border-dashed border-slate-300 dark:border-slate-700">
          <div className="w-16 h-16 bg-white dark:bg-slate-800 rounded-full flex items-center justify-center mx-auto mb-4 text-slate-400">
            <PackageOpen size={32} />
          </div>
          <h3 className="text-lg font-bold text-slate-700 dark:text-slate-300">
            작성한 리뷰가 없습니다
          </h3>
          <p className="text-slate-500 mt-2 text-sm">
            구매한 상품의 리뷰를 남기고 다른 고객에게 도움을 주세요!
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {reviews.map((review) => (
            <div
              key={review.id}
              className="flex flex-col sm:flex-row items-start gap-5 p-5 rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 hover:shadow-md transition-shadow relative group"
            >
              {/* Product Image */}
              <Link
                href={`/product/${review.product_id}`}
                className="w-20 h-20 bg-slate-100 dark:bg-slate-700 rounded-xl overflow-hidden relative flex-shrink-0 border border-slate-200 dark:border-slate-600"
              >
                {review.product_image ? (
                  <Image
                    src={
                      review.product_image.startsWith("http")
                        ? review.product_image
                        : `${apiUrl}${review.product_image}`
                    }
                    alt={review.product_name || "상품"}
                    fill
                    className="object-cover hover:scale-105 transition-transform"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-xs font-bold text-slate-400">
                    LUXAI
                  </div>
                )}
              </Link>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <Link
                  href={`/product/${review.product_id}`}
                  className="font-bold text-slate-900 dark:text-white hover:text-blue-600 transition line-clamp-1"
                >
                  {review.product_name || "상품명 미상"}
                </Link>
                <div className="flex items-center gap-3 mt-1.5 mb-2">
                  {renderStars(review.rating)}
                  <span className="text-xs text-slate-400 font-medium">
                    {new Date(review.created_at).toLocaleDateString("ko-KR")}
                  </span>
                </div>
                {review.content && (
                  <p className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed line-clamp-3">
                    {review.content}
                  </p>
                )}
              </div>

              {/* Delete Button */}
              <button
                onClick={() => handleDelete(review.id)}
                className="absolute top-4 right-4 p-2 text-slate-300 hover:text-red-500 bg-white dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg opacity-0 group-hover:opacity-100 transition-all shadow-sm"
                title="리뷰 삭제"
              >
                <Trash2 size={16} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
