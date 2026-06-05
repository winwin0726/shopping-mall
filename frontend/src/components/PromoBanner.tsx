"use client";

import { useTheme } from "./ThemeProvider";

export default function PromoBanner() {
  const { themeConfig } = useTheme();

  const title = themeConfig.promoCardTitle || "SUMMER SALE";
  const desc = themeConfig.promoCardDesc || "최대 50% 할인 혜택, AI 가상 피팅으로 나만의 스타일을 미리 확인해보세요!";
  const bgImg = themeConfig.promoCardImgUrl || "/promo_banner.png";
  const link = themeConfig.promoCardLinkUrl || "/category/summer-sale";

  return (
    <section className="bg-slate-50 dark:bg-slate-900 border-y border-slate-100 dark:border-slate-800">
      <div 
        className="relative w-full h-[400px] flex items-center justify-center bg-cover bg-center"
        style={{ backgroundImage: `url('${bgImg}')` }}
      >
        <div className="absolute inset-0 bg-black/40" />
        <div className="relative text-center z-10 p-8 bg-white/10 backdrop-blur-md rounded-2xl border border-white/20 shadow-2xl">
          <h2 className="text-4xl md:text-5xl font-extrabold text-white mb-4 tracking-tighter">
            {title}
          </h2>
          <p className="text-lg text-slate-200 mb-8 max-w-xl mx-auto font-medium whitespace-pre-wrap">
            {desc}
          </p>
          <a 
            href={link} 
            className="inline-block px-10 py-4 bg-white text-black rounded-lg font-bold shadow-xl hover:bg-slate-100 hover:scale-105 transition-transform"
          >
            기획전 상품보기
          </a>
        </div>
      </div>
    </section>
  );
}

