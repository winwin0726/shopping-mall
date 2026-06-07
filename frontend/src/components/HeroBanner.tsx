"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { useTheme } from "@/components/ThemeProvider";

export default function HeroBanner() {
  const { themeConfig } = useTheme();

  const getRadiusStyle = (r: string | undefined) => {
    if (r === "none") return "0px";
    if (r === "sm") return "4px";
    if (r === "md") return "8px";
    if (r === "lg") return "16px";
    if (r === "full") return "9999px";
    return "8px";
  };

  const isImageOnly = themeConfig.bannerMode === "image_only" && !!themeConfig.bannerImageOnlyUrl;
  const linkUrl = themeConfig.bannerLinkUrl || "/category/여성의류";

  if (isImageOnly) {
    return (
      <section className="relative h-[50vh] min-h-[400px] overflow-hidden group">
        <Link href={linkUrl} className="block w-full h-full relative cursor-pointer">
          <div
            className="absolute inset-0 bg-cover bg-center transition-transform duration-1000 group-hover:scale-[1.03]"
            style={{ backgroundImage: `url(${themeConfig.bannerImageOnlyUrl})` }}
          />
          <div className="absolute inset-0 bg-black/5 group-hover:bg-black/0 transition-colors duration-500" />
        </Link>
      </section>
    );
  }

  // 1. 배경 설정: 커스텀 이미지가 있으면 사용하고, 없는 경우 AI가 생성한 프리미엄 luxai_hero_bg.png를 기본 사용
  const hasCustomBg = !!themeConfig.bannerBgUrl;
  const bgImageSrc = themeConfig.bannerBgUrl || "/images/luxai_hero_bg.png";
  const bgStyle = { backgroundImage: `url(${bgImageSrc})` };

  // 2. 가독성 및 테마 세팅: 기본 샌드 베이지 배경일 때는 세련된 스톤차콜 텍스트, 
  //    커스텀 배경이 있을 때는 화이트 텍스트를 동적으로 대응하여 미감을 극대화
  const isDefaultBg = !hasCustomBg;
  
  const textTitleClass = isDefaultBg 
    ? "text-stone-900 font-black tracking-tight" 
    : "text-white font-black tracking-tight";
    
  const textSubClass = isDefaultBg 
    ? "text-stone-600 font-medium" 
    : "text-white/80 font-medium";
    
  const badgeClass = isDefaultBg 
    ? "bg-stone-200/50 text-stone-600 border-stone-300/80" 
    : "bg-white/10 text-white border-white/20";

  return (
    <section className="relative h-[50vh] min-h-[400px] flex items-center overflow-hidden">
      {/* 배경 이미지 레이어 */}
      <div
        className="absolute inset-0 bg-cover bg-center transition-all duration-500"
        style={bgStyle}
      />
      
      {/* 커스텀 어두운 배경일 때 그라데이션 어둡게 오버레이 */}
      {hasCustomBg && (
        <div className="absolute inset-0 bg-gradient-to-r from-black/70 via-black/40 to-transparent" />
      )}
      
      {/* 기본 콰이어트 럭셔리 배경일 때 은은한 빛 반사 오버레이 */}
      {isDefaultBg && (
        <div className="absolute inset-0 bg-gradient-to-r from-white/40 via-white/10 to-transparent" />
      )}

      <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 w-full">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
          className="max-w-2xl"
        >
          <span className={`inline-block px-4 py-1.5 backdrop-blur-md text-xs font-bold uppercase tracking-widest rounded-full mb-4 border ${badgeClass}`}>
            2026 S/S LUXAI COLLECTION
          </span>
          <h1 className={`text-4xl sm:text-5xl leading-tight mb-4 ${textTitleClass}`}>
            {themeConfig.bannerTitle || "내 방에서 마주하는 스마트 럭셔리"}
          </h1>
          <p className={`text-base sm:text-lg mb-6 max-w-lg ${textSubClass}`}>
            {themeConfig.bannerSubtitle || "LUXAI 프리미엄 AI 가상 피팅으로 나만의 완벽한 핏과 스타일을 완성하세요."}
          </p>
          
          <div className="flex flex-wrap gap-4">
            <Link
              href="/category/여성의류"
              className="px-6 py-3 text-white font-bold hover:opacity-90 transition text-sm uppercase tracking-wider text-center"
              style={{ 
                backgroundColor: themeConfig.primaryColor || "#2563eb",
                borderRadius: getRadiusStyle(themeConfig.borderRadius)
              }}
            >
              Shop Now
            </Link>
            <Link
              href="/category/남성의류"
              className={`px-6 py-3 border font-bold transition text-sm uppercase tracking-wider text-center ${
                isDefaultBg 
                  ? "border-stone-400 text-stone-700 hover:bg-stone-100/50" 
                  : "border-white/50 text-white hover:bg-white/10"
              }`}
              style={{ 
                borderRadius: getRadiusStyle(themeConfig.borderRadius)
              }}
            >
              Men&apos;s Collection
            </Link>
          </div>
        </motion.div>
      </div>
    </section>
  );
}