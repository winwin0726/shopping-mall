"use client";

import { motion } from 'framer-motion';
import Link from 'next/link';
import { useAuth } from '@/hooks/useAuth';

export type Product = {
  id: number;
  name: string;
  category: 'top' | 'bottom' | 'accessory';
  price: number;
  sale_price?: number;
  discount_rate?: number;
  transparentImage: string; // The URL of the pre-processed no-bg item
};

interface ProductListProps {
  products: Product[];
  onSelect?: (product: Product) => void;
  selectedIds?: number[];
  linkToDetail?: boolean; // true?ﺑﻣ۸ﺑ ? ﮞ„ﺕ ?˜ﮞ ﺑﮞ۶€ﻣ۰??ﺑﻣ ™, false?ﺑﻣ۸ﺑ ﻡﺕﺍﮞ۰ﺑ onSelect ?™ﮞž‘
}

export default function ProductList({ products, onSelect, selectedIds = [], linkToDetail = false }: ProductListProps) {
  const { user } = useAuth();
  const isMasked = user === null || user.grade === 5;

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
      {products.map((product) => {
        const isSelected = selectedIds.includes(product.id);
        
        const card = (
          <motion.div
            key={product.id}
            whileHover={{ y: -5 }}
            onClick={!linkToDetail ? () => onSelect?.(product) : undefined}
            className={`cursor-pointer rounded-2xl p-4 glass-panel border transition-all ${
              isSelected 
                ? 'border-blue-500 shadow-blue-500/20 shadow-lg bg-blue-50/50 dark:bg-blue-900/20' 
                : 'border-slate-200 dark:border-slate-700 hover:border-blue-300'
            }`}
          >
            {/* Aspect Ratio Box for Image */}
            <div className="aspect-[4/5] w-full bg-white dark:bg-slate-800 rounded-xl overflow-hidden mb-3 relative flex items-center justify-center">
              <img 
                src={product.transparentImage} 
                alt={product.name} 
                className="w-3/4 object-contain drop-shadow-md group-hover:scale-105 transition-transform duration-300" 
              />
              {/* ? ﮞ ﺕ ﻣﺍﺍﮞ? */}
              {product.discount_rate && product.discount_rate > 0 && !isMasked && (
                <span className="absolute top-2 left-2 px-2 py-1 bg-red-500 text-white text-[10px] font-extrabold rounded-md shadow-sm">
                  {product.discount_rate}%
                </span>
              )}
            </div>
            
            <div>
              <h3 className="text-sm font-semibold text-slate-800 dark:text-white line-clamp-2 leading-snug">
                {isMasked ? "🔒 가입 후 확인 가능" : product.name}
              </h3>
              <p className="text-xs text-slate-500 mt-1 uppercase">{product.category}</p>
              <div className="flex items-baseline gap-2 mt-2">
                {isMasked ? (
                  <p className="text-slate-400 dark:text-slate-500 font-medium text-xs flex items-center bg-slate-100 dark:bg-slate-800/80 px-2 py-0.5 rounded border border-slate-200/50 dark:border-slate-700/50">
                    <span className="mr-1">🔒</span> 회원전용 가격
                  </p>
                ) : (
                  <>
                    <p className="text-blue-600 dark:text-blue-400 font-bold">
                      ₩{(product.sale_price || product.price).toLocaleString()}
                    </p>
                    {product.sale_price && product.sale_price < product.price && (
                      <p className="text-xs text-slate-400 line-through">
                        ₩{product.price.toLocaleString()}
                      </p>
                    )}
                  </>
                )}
              </div>
            </div>
          </motion.div>
        );

        if (linkToDetail) {
          return (
            <Link key={product.id} href={`/product/${product.id}`}>
              {card}
            </Link>
          );
        }
        
        return <div key={product.id}>{card}</div>;
      })}
    </div>
  );
}

