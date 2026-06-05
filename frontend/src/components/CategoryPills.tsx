"use client";

import Link from "next/link";

const categories = [
  { name: "남성의류", emoji: "👔" },
  { name: "여성의류", emoji: "👗" },
  { name: "가방", emoji: "👜" },
  { name: "지갑", emoji: "💳" },
  { name: "시계", emoji: "⌚" },
  { name: "악세사리", emoji: "💍" },
  { name: "신발", emoji: "👟" },
  { name: "국내배송", emoji: "🚚" },
];

export default function CategoryPills() {
  return (
    <section className="py-8 bg-white dark:bg-slate-900 border-b border-slate-100 dark:border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-center gap-3 overflow-x-auto pb-2 scrollbar-hide">
          {categories.map((cat) => (
            <Link
              key={cat.name}
              href={`/category/${cat.name}`}
              className="flex-shrink-0 flex items-center gap-2 px-5 py-2.5 bg-slate-50 dark:bg-slate-800 hover:bg-blue-50 dark:hover:bg-blue-900/20 border border-slate-200 dark:border-slate-700 rounded-full text-sm font-semibold text-slate-700 dark:text-slate-300 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
            >
              <span>{cat.emoji}</span>
              <span>{cat.name}</span>
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}