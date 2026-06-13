"use client";

import { motion } from "framer-motion";
import { Product } from "./ProductList";
import Image from "next/image";
import Link from "next/link";
import { useTheme } from "@/components/ThemeProvider";
import InlineProductEditor from "./InlineProductEditor";
import { useAuth } from "@/hooks/useAuth";

interface FeaturedProductsProps {
  products: Product[];
  onTryOn: (product: Product) => void;
}

export default function FeaturedProducts({ products, onTryOn }: FeaturedProductsProps) {
  const { themeConfig } = useTheme();
  const { user } = useAuth();
  const isMasked = user === null || user.grade === 5;
  
  // 테마에 따른 그리드 열 개수 매핑
  const getGridColsClass = (cols: number | undefined) => {
    if (cols === 2) return "lg:grid-cols-2";
    if (cols === 4) return "lg:grid-cols-4";
    return "lg:grid-cols-3"; // Default 3
  };

  // 테마에 따른 보더 라운드 매핑
  const getRadiusClass = (r: string | undefined) => {
    if (r === "none") return "rounded-none";
    if (r === "sm") return "rounded-sm";
    if (r === "md") return "rounded-md";
    if (r === "lg") return "rounded-2xl";
    if (r === "full") return "rounded-[32px]";
    return "rounded-lg";
  };

  const isVtonEnabled = themeConfig.features?.enable_vton !== false;

  // gridCols 개수에 맞춰 전시 상품 개수 조절 (예: 4열이면 4개 혹은 8개, 3열이면 3개 혹은 6개)
  const displayLimit = themeConfig.gridCols ? themeConfig.gridCols * 2 : 6;
  const featured = products.slice(0, displayLimit);
  
  if (featured.length === 0) return null;

  return (
    <section className="py-24 transition-colors duration-300" style={{ backgroundColor: themeConfig.backgroundColor }}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-end mb-12">
          <div>
            <span className="uppercase tracking-[0.2em] text-xs font-bold text-slate-500 mb-2 block">
              Curated Selection
            </span>
            <h2 className="text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">
              New Arrivals
            </h2>
          </div>
          <Link 
            href="/category/여성의류" 
            className="text-sm font-semibold hover:opacity-80 transition-colors uppercase tracking-wider hidden sm:block"
            style={{ color: themeConfig.primaryColor || "#2563eb" }}
          >
            View All
          </Link>
        </div>

        <div className={`grid grid-cols-1 sm:grid-cols-2 gap-8 ${getGridColsClass(themeConfig.gridCols)}`}>
          {featured.map((product, idx) => (
            <motion.div
              key={product.id}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: idx * 0.05, duration: 0.5 }}
              className="group relative cursor-pointer"
            >
              <div 
                className={`relative aspect-[3/4] w-full bg-slate-100 dark:bg-slate-800/50 overflow-hidden mb-4 border border-slate-100 dark:border-slate-800 transition-all ${getRadiusClass(themeConfig.borderRadius)}`}
              >
                <div
                  className="w-full h-full bg-contain bg-center bg-no-repeat transition-transform duration-700 group-hover:scale-105"
                  style={{ backgroundImage: `url(${product.transparentImage})` }}
                />
                
                {/* AI 가상 피팅 룸 솔루션 ON인 경우에만 렌더링 */}
                {isVtonEnabled && (
                  <div className="absolute inset-x-0 bottom-0 p-4 opacity-0 group-hover:opacity-100 translate-y-4 group-hover:translate-y-0 transition-all duration-300">
                    <button
                      onClick={(e) => { e.preventDefault(); onTryOn(product); }}
                      className="w-full bg-white/95 backdrop-blur-sm text-black py-3 rounded-md font-bold text-sm shadow-xl hover:bg-opacity-100 transition-colors flex items-center justify-center gap-1.5"
                      style={{ 
                        borderLeft: `4px solid ${themeConfig.primaryColor || '#2563eb'}`,
                        borderRadius: "6px"
                      }}
                    >
                      <span>✨ AI 가상피팅</span>
                    </button>
                  </div>
                )}
              </div>
              <div className="px-1">
                <p className="text-[10px] text-slate-500 uppercase tracking-widest mb-1">{product.category}</p>
                <div className="flex flex-col gap-0.5">
                  <InlineProductEditor
                    productId={product.id}
                    fieldName="kr_name"
                    initialValue={product.name}
                    className="text-base font-bold text-slate-900 dark:text-white truncate"
                  >
                    <Link href={`/product/${product.id}`} className="hover:underline">
                      {isMasked ? "🔒 가입 후 확인 가능" : product.name}
                    </Link>
                  </InlineProductEditor>
                  <InlineProductEditor
                    productId={product.id}
                    fieldName="base_price"
                    initialValue={product.price}
                    className="text-sm font-black mt-1 block"
                    style={{ color: themeConfig.primaryColor || "#2563eb" }}
                  >
                    {isMasked ? "🔒 회원공개 가격" : `₩${product.price.toLocaleString()}`}
                  </InlineProductEditor>
                </div>
              </div>
            </motion.div>
          ))}
        </div>

        <div className="mt-12 text-center sm:hidden">
          <Link 
            href="/category/여성의류" 
            className="inline-block px-8 py-4 border border-slate-300 dark:border-slate-700 text-sm font-bold uppercase tracking-widest text-slate-900 dark:text-white hover:bg-slate-50 dark:hover:bg-slate-800"
            style={{ borderRadius: getRadiusClass(themeConfig.borderRadius) }}
          >
            View All
          </Link>
        </div>
      </div>
    </section>
  );
}