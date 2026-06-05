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
      <section className="relative h-[85vh] min-h-[600px] overflow-hidden group">
        <Link href={linkUrl} className="block w-full h-full relative cursor-pointer">
          <div
            className="absolute inset-0 bg-cover bg-center transition-transform duration-1000 group-hover:scale-[1.03]"
            style={{ backgroundImage: `url(${themeConfig.bannerImageOnlyUrl})` }}
          />
          {/* Subtle gradient overlay on hover for premium styling */}
          <div className="absolute inset-0 bg-black/5 group-hover:bg-black/0 transition-colors duration-500" />
        </Link>
      </section>
    );
  }

  // Fallback / Text & Bg combination mode
  const bgStyle = themeConfig.bannerBgUrl 
    ? { backgroundImage: `url(${themeConfig.bannerBgUrl})` }
    : { backgroundImage: `linear-gradient(135deg, ${themeConfig.primaryColor || "#2563eb"}, ${themeConfig.secondaryColor || "#4f46e5"})` };

  return (
    <section className="relative h-[85vh] min-h-[600px] flex items-center overflow-hidden">
      <div
        className="absolute inset-0 bg-cover bg-center transition-all duration-500"
        style={bgStyle}
      />
      {themeConfig.bannerBgUrl && (
        <div className="absolute inset-0 bg-gradient-to-r from-black/70 via-black/40 to-transparent" />
      )}
      <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 w-full">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
          className="max-w-2xl"
        >
          <span className="inline-block px-4 py-1.5 bg-white/10 backdrop-blur-md text-white text-xs font-bold uppercase tracking-widest rounded-full mb-6 border border-white/20">
            2026 S/S Collection
          </span>
          <h1 className="text-5xl sm:text-7xl font-black text-white leading-tight mb-6">
            {themeConfig.bannerTitle || "Discover Premium Style"}
          </h1>
          <p className="text-lg text-white/70 font-medium mb-8 max-w-lg">
            {themeConfig.bannerSubtitle || "AI 기반 가상 피팅으로 나만의 스타일을 완성하세요. LUXAI에서 트렌드를 선도합니다."}
          </p>
          <div className="flex flex-wrap gap-4">
            <Link
              href="/category/여성의류"
              className="px-8 py-4 text-white font-bold hover:opacity-90 transition text-sm uppercase tracking-wider text-center"
              style={{ 
                backgroundColor: themeConfig.primaryColor || "#2563eb",
                borderRadius: getRadiusStyle(themeConfig.borderRadius)
              }}
            >
              Shop Now
            </Link>
            <Link
              href="/category/남성의류"
              className="px-8 py-4 border-2 border-white/50 text-white font-bold hover:bg-white/10 transition text-sm uppercase tracking-wider text-center"
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