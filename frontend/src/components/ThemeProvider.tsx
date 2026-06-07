"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { API_URL } from "@/lib/api";

export interface ThemeConfig {
  primaryColor?: string;
  secondaryColor?: string;
  backgroundColor?: string;
  fontFamily?: string;
  bannerTitle?: string;
  bannerSubtitle?: string;
  bannerBgUrl?: string;
  bannerMode?: "text_and_bg" | "image_only";
  bannerImageOnlyUrl?: string;
  bannerLinkUrl?: string;
  logoUrl?: string;
  layoutStyle?: string;
  gridCols?: number;
  borderRadius?: string;
  features?: {
    enable_vton?: boolean;
    enable_checkout?: boolean;
    enable_lookbook?: boolean;
    enable_reviews?: boolean;
    enable_autocrawl?: boolean;
  };
  
  // 1. 프로모션 띠 배너 (Promo Strip)
  enablePromo?: boolean;
  promoText?: string;
  promoBgColor?: string;
  promoTextColor?: string;
  promoLinkUrl?: string;

  // 2. 푸터 정보 설정 (Footer Company Info)
  footerCompany?: string;
  footerOwner?: string;
  footerAddress?: string;
  footerTel?: string;
  footerEmail?: string;
  footerBizNum?: string;
  footerReportNum?: string;
  footerCopyright?: string;

  // 3. 메인 하단 프로모션 카드 배너 (Promo Card Banner)
  promoCardTitle?: string;
  promoCardDesc?: string;
  promoCardImgUrl?: string;
  promoCardLinkUrl?: string;
}

interface ThemeContextType {
  themeConfig: ThemeConfig;
  loading: boolean;
  tenantName: string;
}

const defaultTheme: ThemeConfig = {
  primaryColor: "#2563eb",
  secondaryColor: "#4f46e5",
  backgroundColor: "#ffffff",
  fontFamily: "Inter",
  bannerTitle: "세상에 없던 나만의 가상 피팅 룸",
  bannerSubtitle: "클릭 한 번으로 가상에서 마음껏 착용해보세요.",
  bannerBgUrl: "",
  bannerMode: "text_and_bg",
  bannerImageOnlyUrl: "",
  bannerLinkUrl: "/category/여성의류",
  layoutStyle: "modern",
  gridCols: 3,
  borderRadius: "md",
  logoUrl: "",
  features: {
    enable_vton: true,
    enable_checkout: true,
    enable_lookbook: true,
    enable_reviews: true,
    enable_autocrawl: true
  },
  enablePromo: true,
  promoText: "🔥 신규 회원 가입 시 10% 추가 즉시 할인쿠폰 자동 지급!",
  promoBgColor: "#ef4444",
  promoTextColor: "#ffffff",
  promoLinkUrl: "/register",
  footerCompany: "LUXAI 주식회사",
  footerOwner: "홍길동",
  footerAddress: "서울특별시 강남구 테헤란로 123 LUXAI 타워 15층",
  footerTel: "1644-1234",
  footerEmail: "support@luxai.com",
  footerBizNum: "120-81-12345",
  footerReportNum: "제 2026-서울강남-1234호",
  footerCopyright: "© 2026 LUXAI. ALL RIGHTS RESERVED.",
  promoCardTitle: "SUMMER SALE",
  promoCardDesc: "최대 50% 할인 혜택, AI 가상 피팅으로 나만의 스타일을 미리 확인해보세요!",
  promoCardImgUrl: "https://images.unsplash.com/photo-1483985988355-763728e1935b?q=80&w=1200&auto=format&fit=crop",
  promoCardLinkUrl: "/category/summer-sale"
};

const ThemeContext = createContext<ThemeContextType>({
  themeConfig: defaultTheme,
  loading: true,
  tenantName: "LUX AI"
});

export const useTheme = () => useContext(ThemeContext);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [themeConfig, setThemeConfig] = useState<ThemeConfig>(defaultTheme);
  const [tenantName, setTenantName] = useState("LUX AI");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // 1. Google Fonts 동적 주입 (Outfit, Inter, Roboto, Noto Sans KR)
    const linkId = "google-fonts-theme";
    if (!document.getElementById(linkId)) {
      const link = document.createElement("link");
      link.id = linkId;
      link.rel = "stylesheet";
      link.href = "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;900&family=Outfit:wght@300;400;600;700;900&family=Roboto:wght@300;400;500;700;900&family=Noto+Sans+KR:wght@300;400;500;700;900&display=swap";
      document.head.appendChild(link);
    }

    async function loadTheme() {
      try {
        const apiUrl = API_URL;
        const domain = typeof window !== "undefined" ? window.location.host : "hq.mall.com";
        const res = await fetch(`${apiUrl}/api/tenant/theme?domain=${domain}`);
        if (res.ok) {
          const data = await res.json();
          setTenantName(data.name || "LUX AI");
          if (data.theme_config && Object.keys(data.theme_config).length > 0) {
            const mergedTheme = {
              ...defaultTheme,
              ...data.theme_config,
              features: {
                ...defaultTheme.features,
                ...(data.theme_config.features || {})
              }
            };
            setThemeConfig(mergedTheme);
            
            // CSS Variables 인젝션
            const root = document.documentElement;
            const primary = data.theme_config.primaryColor || "#2563eb";
            const secondary = data.theme_config.secondaryColor || "#4f46e5";
            const bg = data.theme_config.backgroundColor || "#ffffff";
            const font = data.theme_config.fontFamily || "Inter";
            
            root.style.setProperty("--primary-color", primary);
            root.style.setProperty("--secondary-color", secondary);
            root.style.setProperty("--background-color", bg);
            root.style.setProperty("--font-family", font);
            
            // Border Radius 매핑
            let radius = "8px";
            const r = data.theme_config.borderRadius || "md";
            if (r === "none") radius = "0px";
            else if (r === "sm") radius = "4px";
            else if (r === "md") radius = "8px";
            else if (r === "lg") radius = "16px";
            else if (r === "full") radius = "9999px";
            root.style.setProperty("--border-radius", radius);
          }
        }
      } catch (error) {
        console.warn("Failed to load tenant theme:", error);
      } finally {
        setLoading(false);
      }
    }
    
    loadTheme();
  }, []);

  return (
    <ThemeContext.Provider value={{ themeConfig, loading, tenantName }}>
      <div style={{ fontFamily: themeConfig.fontFamily || "Inter", backgroundColor: themeConfig.backgroundColor || "transparent" }} className="min-h-screen transition-colors duration-300">
        {children}
      </div>
    </ThemeContext.Provider>
  );
}
