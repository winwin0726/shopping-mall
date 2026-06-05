"use client";
import { authFetch } from "@/lib/api";

import { useEffect, useState } from "react";
import { 
  Palette, Sparkles, ShoppingCart, BookOpen, MessageSquare, Bot, 
  Check, RefreshCw, Layout, Grid, LayoutTemplate, Type, Image as ImageIcon, 
  Sliders, Eye, HelpCircle, Upload, Trash2, Cpu, Sparkle
} from "lucide-react";

interface ThemeConfig {
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
  layoutStyle?: string; // 'modern' | 'gallery' | 'card'
  gridCols?: number; // 2 | 3 | 4
  borderRadius?: string; // 'none' | 'sm' | 'md' | 'lg' | 'full'
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

interface TenantData {
  id: number;
  domain: string;
  name: string;
  theme_config: ThemeConfig;
  is_active: boolean;
}

const PRESETS = [
  {
    name: "럭셔리 골드 & 다크 (Luxury Gold)",
    config: {
      primaryColor: "#d97706",
      secondaryColor: "#1e1b4b",
      backgroundColor: "#0f172a",
      fontFamily: "Outfit",
      bannerTitle: "PREMIUM AI VIRTUAL FITTING",
      bannerSubtitle: "최상의 핏과 럭셔리 스타일을 가상에서 미리 경험해 보세요.",
      bannerBgUrl: "https://images.unsplash.com/photo-1441986300917-64674bd600d8?q=80&w=1200&auto=format&fit=crop",
      logoUrl: "",
      layoutStyle: "gallery",
      gridCols: 3,
      borderRadius: "md",
      features: {
        enable_vton: true,
        enable_checkout: true,
        enable_lookbook: true,
        enable_reviews: true,
        enable_autocrawl: true
      }
    }
  },
  {
    name: "미니멀리즘 화이트 (Minimal White)",
    config: {
      primaryColor: "#18181b",
      secondaryColor: "#71717a",
      backgroundColor: "#ffffff",
      fontFamily: "Inter",
      bannerTitle: "Simply Wear with AI",
      bannerSubtitle: "더 쾌적하고 미니멀한 나만의 가상 옷장.",
      bannerBgUrl: "https://images.unsplash.com/photo-1483985988355-763728e1935b?q=80&w=1200&auto=format&fit=crop",
      logoUrl: "",
      layoutStyle: "modern",
      gridCols: 4,
      borderRadius: "none",
      features: {
        enable_vton: true,
        enable_checkout: true,
        enable_lookbook: true,
        enable_reviews: true,
        enable_autocrawl: true
      }
    }
  },
  {
    name: "비비드 네온 핑크 (Vivid Neon)",
    config: {
      primaryColor: "#ec4899",
      secondaryColor: "#4f46e5",
      backgroundColor: "#030712",
      fontFamily: "Outfit",
      bannerTitle: "NEXT-GEN CLOTHING ROOM",
      bannerSubtitle: "한 번의 터치로 변화하는 트렌디 피팅 솔루션.",
      bannerBgUrl: "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?q=80&w=1200&auto=format&fit=crop",
      logoUrl: "",
      layoutStyle: "card",
      gridCols: 2,
      borderRadius: "lg",
      features: {
        enable_vton: true,
        enable_checkout: true,
        enable_lookbook: true,
        enable_reviews: true,
        enable_autocrawl: true
      }
    }
  },
  {
    name: "에메랄드 클래식 (Classic Emerald)",
    config: {
      primaryColor: "#059669",
      secondaryColor: "#0f766e",
      backgroundColor: "#f8fafc",
      fontFamily: "Roboto",
      bannerTitle: "Classic Comfort Mode",
      bannerSubtitle: "자연스럽고 품격 있는 클래식 패션의 완성.",
      bannerBgUrl: "https://images.unsplash.com/photo-1490481651871-ab68de25d43d?q=80&w=1200&auto=format&fit=crop",
      logoUrl: "",
      layoutStyle: "modern",
      gridCols: 3,
      borderRadius: "full",
      features: {
        enable_vton: true,
        enable_checkout: true,
        enable_lookbook: true,
        enable_reviews: true,
        enable_autocrawl: true
      }
    }
  }
];

export default function DesignTab({ onThemeUpdate }: { onThemeUpdate?: (tenant: any) => void }) {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";
  
  const [tenant, setTenant] = useState<TenantData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saveLoading, setSaveLoading] = useState(false);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [uploadingBannerBg, setUploadingBannerBg] = useState(false);
  const [uploadingBannerImageOnly, setUploadingBannerImageOnly] = useState(false);
  const [aiGenerating, setAiGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // AI Prompt State
  const [aiPrompt, setAiPrompt] = useState("");

  // Theme states
  const [shopName, setShopName] = useState("");
  const [logoUrl, setLogoUrl] = useState("");
  const [primaryColor, setPrimaryColor] = useState("#2563eb");
  const [secondaryColor, setSecondaryColor] = useState("#4f46e5");
  const [backgroundColor, setBackgroundColor] = useState("#ffffff");
  const [fontFamily, setFontFamily] = useState("Inter");
  const [bannerTitle, setBannerTitle] = useState("");
  const [bannerSubtitle, setBannerSubtitle] = useState("");
  const [bannerBgUrl, setBannerBgUrl] = useState("");
  const [bannerMode, setBannerMode] = useState<"text_and_bg" | "image_only">("text_and_bg");
  const [bannerImageOnlyUrl, setBannerImageOnlyUrl] = useState("");
  const [bannerLinkUrl, setBannerLinkUrl] = useState("");
  const [layoutStyle, setLayoutStyle] = useState("modern");
  const [gridCols, setGridCols] = useState(3);
  const [borderRadius, setBorderRadius] = useState("md");

  // Promo Strip States
  const [enablePromo, setEnablePromo] = useState(true);
  const [promoText, setPromoText] = useState("");
  const [promoBgColor, setPromoBgColor] = useState("#ef4444");
  const [promoTextColor, setPromoTextColor] = useState("#ffffff");
  const [promoLinkUrl, setPromoLinkUrl] = useState("");

  // Footer States
  const [footerCompany, setFooterCompany] = useState("");
  const [footerOwner, setFooterOwner] = useState("");
  const [footerAddress, setFooterAddress] = useState("");
  const [footerTel, setFooterTel] = useState("");
  const [footerEmail, setFooterEmail] = useState("");
  const [footerBizNum, setFooterBizNum] = useState("");
  const [footerReportNum, setFooterReportNum] = useState("");
  const [footerCopyright, setFooterCopyright] = useState("");

  // Promo Card Banner States
  const [promoCardTitle, setPromoCardTitle] = useState("");
  const [promoCardDesc, setPromoCardDesc] = useState("");
  const [promoCardImgUrl, setPromoCardImgUrl] = useState("");
  const [promoCardLinkUrl, setPromoCardLinkUrl] = useState("");
  
  const [uploadingPromoCardImg, setUploadingPromoCardImg] = useState(false);

  // Feature Toggles
  const [enableVton, setEnableVton] = useState(true);
  const [enableCheckout, setEnableCheckout] = useState(true);
  const [enableLookbook, setEnableLookbook] = useState(true);
  const [enableReviews, setEnableReviews] = useState(true);
  const [enableAutocrawl, setEnableAutocrawl] = useState(true);

  useEffect(() => {
    fetchTenantTheme();
  }, []);

  const fetchTenantTheme = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await authFetch(`${apiUrl}/api/admin/tenants`);
      if (!res.ok) throw new Error("테넌트 설정을 로드하지 못했습니다.");
      const tenants: TenantData[] = await res.json();
      
      const hq = tenants.find(t => t.domain === "hq.mall.com") || tenants[0];
      if (!hq) throw new Error("등록된 테넌트가 존재하지 않습니다.");

      setTenant(hq);
      setShopName(hq.name || "");
      
      const theme = hq.theme_config || {};
      setLogoUrl(theme.logoUrl || "");
      setPrimaryColor(theme.primaryColor || "#2563eb");
      setSecondaryColor(theme.secondaryColor || "#4f46e5");
      setBackgroundColor(theme.backgroundColor || "#ffffff");
      setFontFamily(theme.fontFamily || "Inter");
      setBannerTitle(theme.bannerTitle || "세상에 없던 나만의 가상 피팅 룸");
      setBannerSubtitle(theme.bannerSubtitle || "클릭 한 번으로 가상에서 마음껏 착용해보세요.");
      setBannerBgUrl(theme.bannerBgUrl || "");
      setBannerMode(theme.bannerMode || "text_and_bg");
      setBannerImageOnlyUrl(theme.bannerImageOnlyUrl || "");
      setBannerLinkUrl(theme.bannerLinkUrl || "");
      setLayoutStyle(theme.layoutStyle || "modern");
      setGridCols(theme.gridCols || 3);
      setBorderRadius(theme.borderRadius || "md");

      // Promo Strip
      setEnablePromo(theme.enablePromo !== false);
      setPromoText(theme.promoText || "🔥 신규 회원 가입 시 10% 추가 즉시 할인쿠폰 자동 지급!");
      setPromoBgColor(theme.promoBgColor || "#ef4444");
      setPromoTextColor(theme.promoTextColor || "#ffffff");
      setPromoLinkUrl(theme.promoLinkUrl || "/register");

      // Footer Info
      setFooterCompany(theme.footerCompany || "LUXAI 주식회사");
      setFooterOwner(theme.footerOwner || "홍길동");
      setFooterAddress(theme.footerAddress || "서울특별시 강남구 테헤란로 123 LUXAI 타워 15층");
      setFooterTel(theme.footerTel || "1644-1234");
      setFooterEmail(theme.footerEmail || "support@luxai.com");
      setFooterBizNum(theme.footerBizNum || "120-81-12345");
      setFooterReportNum(theme.footerReportNum || "제 2026-서울강남-1234호");
      setFooterCopyright(theme.footerCopyright || "© 2026 LUXAI. ALL RIGHTS RESERVED.");

      // Promo Card Banner
      setPromoCardTitle(theme.promoCardTitle || "SUMMER SALE");
      setPromoCardDesc(theme.promoCardDesc || "최대 50% 할인 혜택, AI 가상 피팅으로 나만의 스타일을 미리 확인해보세요!");
      setPromoCardImgUrl(theme.promoCardImgUrl || "https://images.unsplash.com/photo-1483985988355-763728e1935b?q=80&w=1200&auto=format&fit=crop");
      setPromoCardLinkUrl(theme.promoCardLinkUrl || "/category/summer-sale");

      const features = theme.features || {};
      setEnableVton(features.enable_vton !== false);
      setEnableCheckout(features.enable_checkout !== false);
      setEnableLookbook(features.enable_lookbook !== false);
      setEnableReviews(features.enable_reviews !== false);
      setEnableAutocrawl(features.enable_autocrawl !== false);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // 이미지 파일 업로드 공통
  const uploadImageFile = async (file: File): Promise<string> => {
    const formData = new FormData();
    formData.append("file", file);

    const res = await authFetch(`${apiUrl}/api/admin/upload`, {
      method: "POST",
      body: formData,
    });

    if (!res.ok) throw new Error("이미지 업로드에 실패했습니다.");
    const data = await res.json();
    return data.url;
  };

  // 로고 업로드
  const handleLogoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith("image/")) {
      alert("이미지 파일만 업로드할 수 있습니다.");
      return;
    }

    setUploadingLogo(true);
    setSuccessMsg(null);
    setError(null);

    try {
      const url = await uploadImageFile(file);
      setLogoUrl(url);
      setSuccessMsg("로고 사진 업로드 성공! 적용하려면 하단에서 '적용하기'를 클릭하세요.");
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setUploadingLogo(false);
    }
  };

  // 배너 배경 사진 업로드
  const handleBannerBgUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith("image/")) {
      alert("이미지 파일만 업로드할 수 있습니다.");
      return;
    }

    setUploadingBannerBg(true);
    setSuccessMsg(null);
    setError(null);

    try {
      const url = await uploadImageFile(file);
      setBannerBgUrl(url);
      setSuccessMsg("배너 배경 사진 업로드 성공! 적용하려면 하단에서 '적용하기'를 클릭하세요.");
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setUploadingBannerBg(false);
    }
  };

  // 배너 단독 사진 업로드
  const handleBannerImageOnlyUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith("image/")) {
      alert("이미지 파일만 업로드할 수 있습니다.");
      return;
    }

    setUploadingBannerImageOnly(true);
    setSuccessMsg(null);
    setError(null);

    try {
      const url = await uploadImageFile(file);
      setBannerImageOnlyUrl(url);
      setSuccessMsg("배너 단독 사진 업로드 성공! 적용하려면 하단에서 '적용하기'를 클릭하세요.");
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setUploadingBannerImageOnly(false);
    }
  };

  // 프로모션 카드 이미지 업로드
  const handlePromoCardImgUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith("image/")) {
      alert("이미지 파일만 업로드할 수 있습니다.");
      return;
    }

    setUploadingPromoCardImg(true);
    setSuccessMsg(null);
    setError(null);

    try {
      const url = await uploadImageFile(file);
      setPromoCardImgUrl(url);
      setSuccessMsg("프로모션 카드 이미지 업로드 성공! 적용하려면 하단에서 '적용하기'를 클릭하세요.");
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setUploadingPromoCardImg(false);
    }
  };

  // Gemini 2.5 Flash 기반 배너 및 테마 생성
  const handleAIBannerGenerate = async () => {
    if (!aiPrompt.trim()) {
      alert("생성하고 싶은 배너의 분위기나 스타일 프롬프트를 입력해 주세요.");
      return;
    }

    setAiGenerating(true);
    setSuccessMsg(null);
    setError(null);

    try {
      const res = await authFetch(`${apiUrl}/api/admin/banner/ai-generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: aiPrompt }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "AI 배너 생성에 실패했습니다.");
      }

      const generated = await res.json();
      
      // 상태 반영
      if (generated.bannerTitle) setBannerTitle(generated.bannerTitle);
      if (generated.bannerSubtitle) setBannerSubtitle(generated.bannerSubtitle);
      if (generated.primaryColor) setPrimaryColor(generated.primaryColor);
      if (generated.secondaryColor) setSecondaryColor(generated.secondaryColor);
      if (generated.fontFamily) setFontFamily(generated.fontFamily);
      if (generated.layoutStyle) setLayoutStyle(generated.layoutStyle);

      setSuccessMsg("✨ Gemini 2.5 Flash가 추천 카피와 어울리는 컬러 테마를 매핑하여 배너를 구성했습니다! 적용하려면 저장하세요.");
      setTimeout(() => setSuccessMsg(null), 5000);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setAiGenerating(false);
    }
  };

  const applyPreset = (presetConfig: ThemeConfig) => {
    setLogoUrl(presetConfig.logoUrl || "");
    setPrimaryColor(presetConfig.primaryColor || "#2563eb");
    setSecondaryColor(presetConfig.secondaryColor || "#4f46e5");
    setBackgroundColor(presetConfig.backgroundColor || "#ffffff");
    setFontFamily(presetConfig.fontFamily || "Inter");
    setBannerTitle(presetConfig.bannerTitle || "");
    setBannerSubtitle(presetConfig.bannerSubtitle || "");
    setBannerBgUrl(presetConfig.bannerBgUrl || "");
    setBannerMode(presetConfig.bannerMode || "text_and_bg");
    setBannerImageOnlyUrl(presetConfig.bannerImageOnlyUrl || "");
    setBannerLinkUrl(presetConfig.bannerLinkUrl || "");
    setLayoutStyle(presetConfig.layoutStyle || "modern");
    setGridCols(presetConfig.gridCols || 3);
    setBorderRadius(presetConfig.borderRadius || "md");

    // Promo Strip
    setEnablePromo(presetConfig.enablePromo !== false);
    setPromoText(presetConfig.promoText || "🔥 신규 회원 가입 시 10% 추가 즉시 할인쿠폰 자동 지급!");
    setPromoBgColor(presetConfig.promoBgColor || "#ef4444");
    setPromoTextColor(presetConfig.promoTextColor || "#ffffff");
    setPromoLinkUrl(presetConfig.promoLinkUrl || "/register");

    // Footer Info
    setFooterCompany(presetConfig.footerCompany || "LUXAI 주식회사");
    setFooterOwner(presetConfig.footerOwner || "홍길동");
    setFooterAddress(presetConfig.footerAddress || "서울특별시 강남구 테헤란로 123 LUXAI 타워 15층");
    setFooterTel(presetConfig.footerTel || "1644-1234");
    setFooterEmail(presetConfig.footerEmail || "support@luxai.com");
    setFooterBizNum(presetConfig.footerBizNum || "120-81-12345");
    setFooterReportNum(presetConfig.footerReportNum || "제 2026-서울강남-1234호");
    setFooterCopyright(presetConfig.footerCopyright || "© 2026 LUXAI. ALL RIGHTS RESERVED.");

    // Promo Card Banner
    setPromoCardTitle(presetConfig.promoCardTitle || "SUMMER SALE");
    setPromoCardDesc(presetConfig.promoCardDesc || "최대 50% 할인 혜택, AI 가상 피팅으로 나만의 스타일을 미리 확인해보세요!");
    setPromoCardImgUrl(presetConfig.promoCardImgUrl || "https://images.unsplash.com/photo-1483985988355-763728e1935b?q=80&w=1200&auto=format&fit=crop");
    setPromoCardLinkUrl(presetConfig.promoCardLinkUrl || "/category/summer-sale");

    const features = presetConfig.features || {};
    setEnableVton(features.enable_vton !== false);
    setEnableCheckout(features.enable_checkout !== false);
    setEnableLookbook(features.enable_lookbook !== false);
    setEnableReviews(features.enable_reviews !== false);
    setEnableAutocrawl(features.enable_autocrawl !== false);

    setSuccessMsg("프리셋 스타일이 로컬 프리뷰에 반영되었습니다. 저장하려면 아래 '적용하기'를 누르세요.");
    setTimeout(() => setSuccessMsg(null), 3000);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!tenant) return;

    setSaveLoading(true);
    setSuccessMsg(null);
    setError(null);

    const payload = {
      name: shopName,
      domain: tenant.domain,
      theme_config: {
        logoUrl,
        primaryColor,
        secondaryColor,
        backgroundColor,
        fontFamily,
        bannerTitle,
        bannerSubtitle,
        bannerBgUrl,
        bannerMode,
        bannerImageOnlyUrl,
        bannerLinkUrl,
        layoutStyle,
        gridCols,
        borderRadius,
        enablePromo,
        promoText,
        promoBgColor,
        promoTextColor,
        promoLinkUrl,
        footerCompany,
        footerOwner,
        footerAddress,
        footerTel,
        footerEmail,
        footerBizNum,
        footerReportNum,
        footerCopyright,
        promoCardTitle,
        promoCardDesc,
        promoCardImgUrl,
        promoCardLinkUrl,
        features: {
          enable_vton: enableVton,
          enable_checkout: enableCheckout,
          enable_lookbook: enableLookbook,
          enable_reviews: enableReviews,
          enable_autocrawl: enableAutocrawl
        }
      },
      is_active: tenant.is_active
    };

    try {
      const res = await authFetch(`${apiUrl}/api/admin/tenants/${tenant.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "디자인 테마를 저장하지 못했습니다.");
      }

      setSuccessMsg("🎉 메인페이지 디자인 및 로고 설정이 성공적으로 배포되었습니다!");
      setTimeout(() => setSuccessMsg(null), 4000);
      
      const updatedData = await res.json();
      if (updatedData.tenant) {
        setTenant(updatedData.tenant);
        setShopName(updatedData.tenant.name);
        if (onThemeUpdate) {
          onThemeUpdate(updatedData.tenant);
        }
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSaveLoading(false);
    }
  };

  const getRadiusClass = (r: string) => {
    if (r === "none") return "rounded-none";
    if (r === "sm") return "rounded-sm";
    if (r === "md") return "rounded-md";
    if (r === "lg") return "rounded-xl";
    if (r === "full") return "rounded-3xl";
    return "rounded-lg";
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-slate-400">
        <RefreshCw className="animate-spin text-blue-500 mb-4" size={36} />
        <p className="text-sm">쇼핑몰 브랜딩 설정 데이터를 조회하는 중입니다...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Top Title & Info */}
      <div className="flex justify-between items-start border-b border-slate-800 pb-4">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            <Palette className="text-blue-500" /> 디자인 & 로고 제어 센터
          </h2>
          <p className="text-slate-400 text-sm mt-1">
            메인 페이지의 테마 컬러, 로고 파일, 배너 텍스트, 상품 레이아웃 배치를 한 곳에서 실시간 편집합니다.
          </p>
        </div>
        <div className="text-xs bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-lg">
          <span className="text-slate-500">도메인:</span> <span className="text-blue-400 font-mono font-bold">{tenant?.domain}</span>
        </div>
      </div>

      {/* Success / Error Alerts */}
      {successMsg && (
        <div className="bg-emerald-950/40 border border-emerald-800 text-emerald-300 p-4 rounded-xl flex items-center animate-in slide-in-from-top-2 duration-200">
          <Check className="mr-3 text-emerald-400 shrink-0" size={20} />
          <span className="text-sm font-medium">{successMsg}</span>
        </div>
      )}
      {error && (
        <div className="bg-red-950/40 border border-red-800 text-red-300 p-4 rounded-xl flex items-center">
          <span className="mr-3 text-red-400 font-bold">⚠️</span>
          <span className="text-sm font-medium">{error}</span>
        </div>
      )}

      {/* Main Grid: Editor on Left (60%), Live Preview on Right (40%) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        
        {/* LEFT: Editor Forms */}
        <form onSubmit={handleSubmit} className="lg:col-span-7 space-y-6">
          
          {/* AI Banner Copywriter Widget (Gemini 2.5 Flash) */}
          <div className="bg-slate-900 border border-slate-800/80 rounded-xl p-5 space-y-4 relative overflow-hidden">
            <div className="absolute top-0 right-0 w-24 h-24 bg-blue-500/5 blur-xl rounded-full"></div>
            
            <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
              <Cpu size={16} className="text-blue-400" /> 
              Gemini 2.5 Flash 메인 배너 AI 카피라이팅 & 테마 자동 빌더
            </h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              원하는 분위기(예: &quot;상큼한 오렌지 톤의 비치웨어 시즌오프 특별 할인 배너&quot;)를 입력하시면, AI가 배너 대제목, 소제목 및 조화로운 컬러 테마를 즉각 자동 생성합니다.
            </p>

            <div className="space-y-3">
              <textarea
                value={aiPrompt}
                onChange={(e) => setAiPrompt(e.target.value)}
                placeholder="어떤 느낌의 배너를 생성하고 싶으신가요? (예: 시원한 여름 바다 휴양지 분위기의 프리미엄 가방 전시 배너)"
                rows={3}
                className="w-full bg-slate-950 border border-slate-850 rounded-xl p-3 text-xs text-white placeholder-slate-700 focus:outline-none focus:border-blue-600 transition resize-none leading-relaxed"
                disabled={aiGenerating}
              />
              
              <button
                type="button"
                onClick={handleAIBannerGenerate}
                disabled={aiGenerating}
                className="w-full bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-bold py-2.5 rounded-xl text-xs flex justify-center items-center gap-1.5 transition-all shadow-md shadow-blue-500/10 disabled:opacity-40"
              >
                {aiGenerating ? (
                  <>
                    <RefreshCw className="animate-spin" size={14} /> Gemini AI가 배너 디자인 생성 중...
                  </>
                ) : (
                  <>
                    <Sparkles size={14} /> Gemini 2.5 Flash로 AI 배너 즉시 생성
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Preset Styles */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
            <h3 className="text-sm font-bold text-slate-300 flex items-center gap-2">
              <LayoutTemplate size={16} className="text-amber-500" /> 원클릭 테마 디자인 프리셋 (Presets)
            </h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              조화롭게 선별된 고품격 폰트와 컬러 세트입니다. 클릭하면 즉시 프리뷰에 세팅됩니다.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 pt-1">
              {PRESETS.map((preset, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => applyPreset(preset.config)}
                  className="bg-slate-950 hover:bg-slate-800 border border-slate-800 hover:border-slate-700 text-left p-3 rounded-lg transition-all text-xs flex flex-col gap-1.5"
                >
                  <span className="font-bold text-slate-200">{preset.name}</span>
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: preset.config.primaryColor }} />
                    <span className="text-[10px] text-slate-500 font-mono">{preset.config.fontFamily} / {preset.config.layoutStyle}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Shop Name & Logo Settings */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
            <h3 className="text-sm font-bold text-slate-300 flex items-center gap-2">
              <Type size={16} className="text-blue-500" /> 쇼핑몰 로고명 및 이미지 파일 변경
            </h3>
            
            <div className="space-y-3">
              <div className="space-y-1.5">
                <label className="text-xs text-slate-400 font-medium">통합 쇼핑몰 이름 (회사명)</label>
                <input
                  type="text"
                  value={shopName}
                  onChange={(e) => setShopName(e.target.value)}
                  placeholder="예: AI 가상피팅 스마트몰"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-700 focus:outline-none focus:border-blue-600 transition"
                  required
                />
              </div>

              {/* Logo Upload Block */}
              <div className="bg-slate-950/45 border border-slate-850 p-4 rounded-xl space-y-3">
                <div className="flex items-center justify-between">
                  <label className="text-xs text-slate-300 font-medium flex items-center gap-1.5">
                    <ImageIcon size={14} className="text-blue-400" /> 대표 로고 이미지 설정
                  </label>
                  {uploadingLogo && <span className="text-[10px] text-blue-500 animate-pulse">로고 사진 업로드 중...</span>}
                </div>

                {logoUrl && (
                  <div className="flex items-center gap-3 bg-slate-900 p-2.5 rounded-lg border border-slate-800">
                    <div className="bg-white p-1 rounded">
                      <img src={logoUrl} alt="Logo" className="h-6 max-w-[120px] object-contain" />
                    </div>
                    <span className="text-[10px] text-slate-500 truncate flex-1 font-mono">{logoUrl}</span>
                    <button
                      type="button"
                      onClick={() => setLogoUrl("")}
                      className="text-red-400 hover:text-red-300 hover:bg-red-950/20 p-1.5 rounded transition"
                      title="로고 제거"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                )}

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                  <div className="space-y-1">
                    <span className="text-[10px] text-slate-500 block">로고 이미지 URL 직접 입력</span>
                    <input
                      type="text"
                      value={logoUrl}
                      onChange={(e) => setLogoUrl(e.target.value)}
                      placeholder="https://example.com/logo.png"
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-700 focus:outline-none focus:border-blue-600 transition font-mono"
                    />
                  </div>

                  <div className="space-y-1">
                    <span className="text-[10px] text-slate-500 block">컴퓨터 사진 파일 첨부</span>
                    <label className="w-full bg-slate-900 hover:bg-slate-855 border border-slate-855 hover:border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-300 hover:text-white flex items-center justify-center gap-1.5 cursor-pointer transition h-[36px] font-semibold">
                      <Upload size={14} className="text-blue-500" />
                      {uploadingLogo ? "업로드 중..." : "로고 사진 첨부하기"}
                      <input
                        type="file"
                        accept="image/*"
                        onChange={handleLogoUpload}
                        className="hidden"
                        disabled={uploadingLogo}
                      />
                    </label>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Main Hero Banner Settings */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
            <div className="flex justify-between items-center border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-slate-300 flex items-center gap-2">
                <ImageIcon size={16} className="text-blue-500" /> 메인 히어로 배너 설정
              </h3>
              <div className="flex bg-slate-950 p-0.5 rounded-lg border border-slate-850 shrink-0">
                <button
                  type="button"
                  onClick={() => setBannerMode("text_and_bg")}
                  className={`px-3 py-1.5 rounded-md text-[10px] font-bold transition-all ${
                    bannerMode === "text_and_bg"
                      ? "bg-blue-600 text-white shadow-sm"
                      : "text-slate-500 hover:text-slate-350"
                  }`}
                >
                  글자 + 배경 조합
                </button>
                <button
                  type="button"
                  onClick={() => setBannerMode("image_only")}
                  className={`px-3 py-1.5 rounded-md text-[10px] font-bold transition-all ${
                    bannerMode === "image_only"
                      ? "bg-blue-600 text-white shadow-sm"
                      : "text-slate-500 hover:text-slate-350"
                  }`}
                >
                  사진 파일 단독 첨부
                </button>
              </div>
            </div>
            
            {bannerMode === "text_and_bg" ? (
              <div className="space-y-3 animate-in fade-in duration-200">
                <div className="space-y-1.5">
                  <label className="text-xs text-slate-400 font-medium">배너 메인 대제목 (Banner Title)</label>
                  <input
                    type="text"
                    value={bannerTitle}
                    onChange={(e) => setBannerTitle(e.target.value)}
                    placeholder="예: 세상에 없던 나만의 가상 피팅 룸"
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-750 focus:outline-none focus:border-blue-600 transition"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs text-slate-400 font-medium">배너 상세 소제목 (Banner Subtitle)</label>
                  <textarea
                    value={bannerSubtitle}
                    onChange={(e) => setBannerSubtitle(e.target.value)}
                    placeholder="예: 클릭 한 번으로 가상에서 마음껏 착용해보세요."
                    rows={2}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-750 focus:outline-none focus:border-blue-600 transition resize-none font-sans"
                  />
                </div>

                {/* Banner Background Image Upload Box */}
                <div className="bg-slate-950/45 border border-slate-850 p-4 rounded-xl space-y-3">
                  <div className="flex items-center justify-between">
                    <label className="text-xs text-slate-300 font-medium flex items-center gap-1.5">
                      <ImageIcon size={14} className="text-blue-400" /> 배너 배경 이미지 설정
                    </label>
                    {uploadingBannerBg && <span className="text-[10px] text-blue-500 animate-pulse">배너 배경 사진 업로드 중...</span>}
                  </div>

                  {bannerBgUrl && (
                    <div className="flex items-center gap-3 bg-slate-900 p-2.5 rounded-lg border border-slate-800">
                      <img src={bannerBgUrl} alt="Banner Background" className="h-8 w-16 object-cover rounded" />
                      <span className="text-[10px] text-slate-500 truncate flex-1 font-mono">{bannerBgUrl}</span>
                      <button
                        type="button"
                        onClick={() => setBannerBgUrl("")}
                        className="text-red-400 hover:text-red-300 hover:bg-red-950/20 p-1.5 rounded transition"
                        title="배경 제거"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  )}

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                    <div className="space-y-1">
                      <span className="text-[10px] text-slate-500 block">배경 이미지 URL 직접 입력</span>
                      <input
                        type="text"
                        value={bannerBgUrl}
                        onChange={(e) => setBannerBgUrl(e.target.value)}
                        placeholder="https://images.unsplash.com/..."
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-700 focus:outline-none focus:border-blue-600 transition font-mono"
                      />
                    </div>

                    <div className="space-y-1">
                      <span className="text-[10px] text-slate-500 block">컴퓨터 사진 파일 첨부</span>
                      <label className="w-full bg-slate-900 hover:bg-slate-855 border border-slate-855 hover:border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-300 hover:text-white flex items-center justify-center gap-1.5 cursor-pointer transition h-[36px] font-semibold">
                        <Upload size={14} className="text-blue-500" />
                        {uploadingBannerBg ? "업로드 중..." : "배경 사진 첨부하기"}
                        <input
                          type="file"
                          accept="image/*"
                          onChange={handleBannerBgUpload}
                          className="hidden"
                          disabled={uploadingBannerBg}
                        />
                      </label>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="space-y-3 animate-in fade-in duration-200">
                {/* Banner Image Only Upload Box */}
                <div className="bg-slate-950/45 border border-slate-850 p-4 rounded-xl space-y-3">
                  <div className="flex items-center justify-between">
                    <label className="text-xs text-slate-300 font-medium flex items-center gap-1.5">
                      <ImageIcon size={14} className="text-blue-400" /> 메인배너 전용 사진 설정
                    </label>
                    {uploadingBannerImageOnly && <span className="text-[10px] text-blue-500 animate-pulse">배너 사진 업로드 중...</span>}
                  </div>

                  {bannerImageOnlyUrl ? (
                    <div className="flex items-center gap-3 bg-slate-900 p-2.5 rounded-lg border border-slate-800">
                      <img src={bannerImageOnlyUrl} alt="Banner Image Only" className="h-8 w-16 object-cover rounded" />
                      <span className="text-[10px] text-slate-500 truncate flex-1 font-mono">{bannerImageOnlyUrl}</span>
                      <button
                        type="button"
                        onClick={() => setBannerImageOnlyUrl("")}
                        className="text-red-400 hover:text-red-300 hover:bg-red-950/20 p-1.5 rounded transition"
                        title="배너 사진 제거"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  ) : (
                    <div className="border border-dashed border-slate-800 rounded-lg p-5 flex flex-col items-center justify-center text-slate-500 bg-slate-950/50">
                      <ImageIcon size={24} className="text-slate-600 mb-1.5" />
                      <p className="text-[10px]">등록된 메인배너 사진이 없습니다. 아래에서 사진을 첨부해 주세요.</p>
                    </div>
                  )}

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                    <div className="space-y-1">
                      <span className="text-[10px] text-slate-500 block">배너 이미지 URL 직접 입력</span>
                      <input
                        type="text"
                        value={bannerImageOnlyUrl}
                        onChange={(e) => setBannerImageOnlyUrl(e.target.value)}
                        placeholder="https://example.com/banner.png"
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-700 focus:outline-none focus:border-blue-600 transition font-mono"
                      />
                    </div>

                    <div className="space-y-1">
                      <span className="text-[10px] text-slate-500 block">컴퓨터 사진 파일 간편 첨부</span>
                      <label className="w-full bg-slate-900 hover:bg-slate-855 border border-slate-855 hover:border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-300 hover:text-white flex items-center justify-center gap-1.5 cursor-pointer transition h-[36px] font-semibold">
                        <Upload size={14} className="text-blue-500" />
                        {uploadingBannerImageOnly ? "업로드 중..." : "배너 사진 첨부하기"}
                        <input
                          type="file"
                          accept="image/*"
                          onChange={handleBannerImageOnlyUpload}
                          className="hidden"
                          disabled={uploadingBannerImageOnly}
                        />
                      </label>
                    </div>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs text-slate-400 font-medium">배너 클릭 시 이동 링크 (Connection Link URL)</label>
                  <input
                    type="text"
                    value={bannerLinkUrl}
                    onChange={(e) => setBannerLinkUrl(e.target.value)}
                    placeholder="예: /category/남성의류 또는 /products/12"
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-700 focus:outline-none focus:border-blue-600 transition font-mono"
                  />
                  <p className="text-[10px] text-slate-500">배너 사진 클릭 시 이동시킬 상품 경로 또는 카테고리 기획전 주소입니다.</p>
                </div>
              </div>
            )}
          </div>
          {/* Color & Typography */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
            <h3 className="text-sm font-bold text-slate-300 flex items-center gap-2">
              <Sliders size={16} className="text-blue-500" /> 브랜드 컬러 & 타이포그래피 설정
            </h3>
            
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {/* Primary Color */}
              <div className="space-y-1.5">
                <label className="text-xs text-slate-400 font-medium">메인 테마 컬러 (Primary)</label>
                <div className="flex gap-2">
                  <input
                    type="color"
                    value={primaryColor}
                    onChange={(e) => setPrimaryColor(e.target.value)}
                    className="w-10 h-10 bg-transparent border-0 cursor-pointer rounded overflow-hidden shrink-0"
                  />
                  <input
                    type="text"
                    value={primaryColor}
                    onChange={(e) => setPrimaryColor(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2 py-1 text-xs text-white focus:outline-none focus:border-blue-600 transition font-mono uppercase"
                  />
                </div>
              </div>

              {/* Secondary Color */}
              <div className="space-y-1.5">
                <label className="text-xs text-slate-400 font-medium">보조 테마 컬러 (Secondary)</label>
                <div className="flex gap-2">
                  <input
                    type="color"
                    value={secondaryColor}
                    onChange={(e) => setSecondaryColor(e.target.value)}
                    className="w-10 h-10 bg-transparent border-0 cursor-pointer rounded overflow-hidden shrink-0"
                  />
                  <input
                    type="text"
                    value={secondaryColor}
                    onChange={(e) => setSecondaryColor(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2 py-1 text-xs text-white focus:outline-none focus:border-blue-600 transition font-mono uppercase"
                  />
                </div>
              </div>

              {/* Background Color */}
              <div className="space-y-1.5">
                <label className="text-xs text-slate-400 font-medium">쇼핑몰 배경 컬러 (Background)</label>
                <div className="flex gap-2">
                  <input
                    type="color"
                    value={backgroundColor}
                    onChange={(e) => setBackgroundColor(e.target.value)}
                    className="w-10 h-10 bg-transparent border-0 cursor-pointer rounded overflow-hidden shrink-0"
                  />
                  <input
                    type="text"
                    value={backgroundColor}
                    onChange={(e) => setBackgroundColor(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2 py-1 text-xs text-white focus:outline-none focus:border-blue-600 transition font-mono uppercase"
                  />
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
              {/* Font Family */}
              <div className="space-y-1.5">
                <label className="text-xs text-slate-400 font-medium flex items-center gap-1">
                  <Type size={12} /> 기본 폰트 패밀리
                </label>
                <select
                  value={fontFamily}
                  onChange={(e) => setFontFamily(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-600 transition"
                >
                  <option value="Inter">Inter (깔끔한 기본 영문/한글)</option>
                  <option value="Outfit">Outfit (트렌디 럭셔리)</option>
                  <option value="Roboto">Roboto (정통 테크형)</option>
                  <option value="Noto Sans KR">Noto Sans KR (부드러운 한글)</option>
                </select>
              </div>

              {/* Border Radius */}
              <div className="space-y-1.5">
                <label className="text-xs text-slate-400 font-medium">UI 컴포넌트 둥글기 (Border Radius)</label>
                <select
                  value={borderRadius}
                  onChange={(e) => setBorderRadius(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-600 transition"
                >
                  <option value="none">사각형 각짐 (Sharp/None)</option>
                  <option value="sm">둥글기 작음 (Small)</option>
                  <option value="md">둥글기 보통 (Medium)</option>
                  <option value="lg">둥글기 크게 (Large/Card)</option>
                  <option value="full">타원형 매우 둥금 (Round/Classic)</option>
                </select>
              </div>
            </div>
          </div>

          {/* Grid Layout & Style Controls */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
            <h3 className="text-sm font-bold text-slate-300 flex items-center gap-2">
              <Layout size={16} className="text-blue-500" /> 메인 상품 레이아웃 & 그리드
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-xs text-slate-400 font-medium">레이아웃 스타일</label>
                <select
                  value={layoutStyle}
                  onChange={(e) => setLayoutStyle(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-600 transition"
                >
                  <option value="modern">기본 모던 그리드형 (Modern Grid)</option>
                  <option value="gallery">AI 룩북 갤러리 강조형 (AI Gallery)</option>
                  <option value="card">미니멀 와이드 카드형 (Wide Card)</option>
                </select>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs text-slate-400 font-medium flex items-center gap-1">
                  <Grid size={12} /> 데스크톱 그리드 열 개수 (Grid Cols)
                </label>
                <div className="flex gap-4 pt-1.5">
                  {[2, 3, 4].map((num) => (
                    <label key={num} className="flex items-center gap-1.5 text-xs text-slate-300 cursor-pointer select-none">
                      <input
                        type="radio"
                        name="gridColsEditor"
                        value={num}
                        checked={gridCols === num}
                        onChange={() => setGridCols(num)}
                        className="w-3.5 h-3.5 border-slate-800 text-blue-600 bg-slate-950 focus:ring-0"
                      />
                      {num}열 배치
                    </label>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* 상단 프로모션 띠 배너 설정 */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
            <div className="flex justify-between items-center border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-slate-300 flex items-center gap-2">
                <Sparkle size={16} className="text-red-500" /> 상단 프로모션 띠 배너 설정
              </h3>
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={enablePromo}
                  onChange={(e) => setEnablePromo(e.target.checked)}
                  className="w-4 h-4 rounded border-slate-800 text-blue-600 bg-slate-950 focus:ring-0"
                />
                <span className="text-xs text-slate-400 font-semibold">사용 여부</span>
              </label>
            </div>

            {enablePromo && (
              <div className="space-y-3.5 animate-in fade-in duration-200">
                <div className="space-y-1.5">
                  <label className="text-xs text-slate-400 font-medium">띠 배너 홍보 문구</label>
                  <input
                    type="text"
                    value={promoText}
                    onChange={(e) => setPromoText(e.target.value)}
                    placeholder="예: 🔥 신규 회원 가입 시 10% 추가 즉시 할인쿠폰 자동 지급!"
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-700 focus:outline-none focus:border-blue-600 transition"
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-xs text-slate-400 font-medium">배경 색상 (Bg Color)</label>
                    <div className="flex gap-2">
                      <input
                        type="color"
                        value={promoBgColor}
                        onChange={(e) => setPromoBgColor(e.target.value)}
                        className="w-10 h-10 bg-transparent border-0 cursor-pointer rounded overflow-hidden shrink-0"
                      />
                      <input
                        type="text"
                        value={promoBgColor}
                        onChange={(e) => setPromoBgColor(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2 py-1 text-xs text-white focus:outline-none focus:border-blue-600 transition font-mono uppercase"
                      />
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs text-slate-400 font-medium">글자 색상 (Text Color)</label>
                    <div className="flex gap-2">
                      <input
                        type="color"
                        value={promoTextColor}
                        onChange={(e) => setPromoTextColor(e.target.value)}
                        className="w-10 h-10 bg-transparent border-0 cursor-pointer rounded overflow-hidden shrink-0"
                      />
                      <input
                        type="text"
                        value={promoTextColor}
                        onChange={(e) => setPromoTextColor(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2 py-1 text-xs text-white focus:outline-none focus:border-blue-600 transition font-mono uppercase"
                      />
                    </div>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs text-slate-400 font-medium">클릭 시 이동 링크 URL</label>
                  <input
                    type="text"
                    value={promoLinkUrl}
                    onChange={(e) => setPromoLinkUrl(e.target.value)}
                    placeholder="예: /register 또는 /category/event"
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-700 focus:outline-none focus:border-blue-600 transition font-mono"
                  />
                </div>
              </div>
            )}
          </div>

          {/* 메인 하단 프로모션 카드 배너 설정 */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
            <h3 className="text-sm font-bold text-slate-300 flex items-center gap-2">
              <ImageIcon size={16} className="text-blue-500" /> 메인 하단 프로모션 카드 배너 설정
            </h3>

            <div className="space-y-3.5">
              <div className="space-y-1.5">
                <label className="text-xs text-slate-400 font-medium">카드 배너 대제목</label>
                <input
                  type="text"
                  value={promoCardTitle}
                  onChange={(e) => setPromoCardTitle(e.target.value)}
                  placeholder="예: SUMMER SALE"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-750 focus:outline-none focus:border-blue-600 transition"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs text-slate-400 font-medium">카드 배너 설명글 (줄바꿈 가능)</label>
                <textarea
                  value={promoCardDesc}
                  onChange={(e) => setPromoCardDesc(e.target.value)}
                  placeholder="예: 최대 50% 할인 혜택, AI 가상 피팅으로 나만의 스타일을 미리 확인해보세요!"
                  rows={2}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-750 focus:outline-none focus:border-blue-600 transition resize-none font-sans"
                />
              </div>

              {/* Promo Card Image Upload Box */}
              <div className="bg-slate-950/45 border border-slate-850 p-4 rounded-xl space-y-3">
                <div className="flex items-center justify-between">
                  <label className="text-xs text-slate-300 font-medium flex items-center gap-1.5">
                    <ImageIcon size={14} className="text-blue-400" /> 카드 배경 이미지 설정
                  </label>
                  {uploadingPromoCardImg && <span className="text-[10px] text-blue-500 animate-pulse">사진 업로드 중...</span>}
                </div>

                {promoCardImgUrl && (
                  <div className="flex items-center gap-3 bg-slate-900 p-2.5 rounded-lg border border-slate-800">
                    <img src={promoCardImgUrl} alt="Promo Card Bg" className="h-8 w-16 object-cover rounded" />
                    <span className="text-[10px] text-slate-500 truncate flex-1 font-mono">{promoCardImgUrl}</span>
                    <button
                      type="button"
                      onClick={() => setPromoCardImgUrl("")}
                      className="text-red-400 hover:text-red-300 hover:bg-red-950/20 p-1.5 rounded transition"
                      title="이미지 제거"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                )}

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                  <div className="space-y-1">
                    <span className="text-[10px] text-slate-500 block">이미지 URL 직접 입력</span>
                    <input
                      type="text"
                      value={promoCardImgUrl}
                      onChange={(e) => setPromoCardImgUrl(e.target.value)}
                      placeholder="https://images.unsplash.com/..."
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-700 focus:outline-none focus:border-blue-600 transition font-mono"
                    />
                  </div>

                  <div className="space-y-1">
                    <span className="text-[10px] text-slate-500 block">컴퓨터 사진 파일 첨부</span>
                    <label className="w-full bg-slate-900 hover:bg-slate-855 border border-slate-855 hover:border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-300 hover:text-white flex items-center justify-center gap-1.5 cursor-pointer transition h-[36px] font-semibold">
                      <Upload size={14} className="text-blue-500" />
                      {uploadingPromoCardImg ? "업로드 중..." : "배경 사진 첨부하기"}
                      <input
                        type="file"
                        accept="image/*"
                        onChange={handlePromoCardImgUpload}
                        className="hidden"
                        disabled={uploadingPromoCardImg}
                      />
                    </label>
                  </div>
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs text-slate-400 font-medium">클릭 시 이동 링크 URL</label>
                <input
                  type="text"
                  value={promoCardLinkUrl}
                  onChange={(e) => setPromoCardLinkUrl(e.target.value)}
                  placeholder="예: /category/summer-sale"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-700 focus:outline-none focus:border-blue-600 transition font-mono"
                />
              </div>
            </div>
          </div>

          {/* 푸터 사업자 정보 설정 */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
            <h3 className="text-sm font-bold text-slate-300 flex items-center gap-2">
              <Layout size={16} className="text-blue-500" /> 푸터 사업자 정보 설정
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-xs text-slate-400 font-medium">상호명 (회사명)</label>
                <input
                  type="text"
                  value={footerCompany}
                  onChange={(e) => setFooterCompany(e.target.value)}
                  placeholder="예: LUXAI 주식회사"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-600 transition"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs text-slate-400 font-medium">대표자명</label>
                <input
                  type="text"
                  value={footerOwner}
                  onChange={(e) => setFooterOwner(e.target.value)}
                  placeholder="예: 홍길동"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-600 transition"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs text-slate-400 font-medium">회사 주소</label>
              <input
                type="text"
                value={footerAddress}
                onChange={(e) => setFooterAddress(e.target.value)}
                placeholder="예: 서울시 강남구 테헤란로 123"
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-600 transition"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-xs text-slate-400 font-medium">대표 전화번호</label>
                <input
                  type="text"
                  value={footerTel}
                  onChange={(e) => setFooterTel(e.target.value)}
                  placeholder="예: 1644-1234"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-600 transition"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs text-slate-400 font-medium">고객문의 이메일 주소</label>
                <input
                  type="email"
                  value={footerEmail}
                  onChange={(e) => setFooterEmail(e.target.value)}
                  placeholder="예: support@luxai.com"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-600 transition"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-xs text-slate-400 font-medium">사업자 등록 번호</label>
                <input
                  type="text"
                  value={footerBizNum}
                  onChange={(e) => setFooterBizNum(e.target.value)}
                  placeholder="예: 120-81-12345"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-600 transition font-mono"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs text-slate-400 font-medium">통신판매업 신고 번호</label>
                <input
                  type="text"
                  value={footerReportNum}
                  onChange={(e) => setFooterReportNum(e.target.value)}
                  placeholder="예: 제 2026-서울강남-1234호"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-600 transition"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs text-slate-400 font-medium">하단 저작권 표시 (Copyright)</label>
              <input
                type="text"
                value={footerCopyright}
                onChange={(e) => setFooterCopyright(e.target.value)}
                placeholder="© 2026 LUXAI. ALL RIGHTS RESERVED."
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-600 transition"
              />
            </div>
          </div>

          {/* Solution Feature Control */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
            <h3 className="text-sm font-bold text-slate-300 flex items-center gap-2">
              <Bot size={16} className="text-blue-500" /> 상세 솔루션 기능 노출 (Feature Control)
            </h3>
            <p className="text-xs text-slate-500">
              메인페이지와 상세페이지에 노출될 인공지능 솔루션 및 부가 기능 스위치입니다.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
              {/* Feature: VTON */}
              <label className="flex items-center justify-between p-3 bg-slate-950 border border-slate-800 rounded-lg cursor-pointer hover:border-slate-700 transition">
                <div className="flex items-center gap-2">
                  <Sparkles size={14} className="text-purple-400" />
                  <span className="text-xs font-semibold text-slate-300">AI 가상 피팅 활성화</span>
                </div>
                <input
                  type="checkbox"
                  checked={enableVton}
                  onChange={(e) => setEnableVton(e.target.checked)}
                  className="w-4 h-4 rounded border-slate-800 text-blue-600 bg-slate-900"
                />
              </label>

              {/* Feature: Checkout */}
              <label className="flex items-center justify-between p-3 bg-slate-950 border border-slate-800 rounded-lg cursor-pointer hover:border-slate-700 transition">
                <div className="flex items-center gap-2">
                  <ShoppingCart size={14} className="text-blue-400" />
                  <span className="text-xs font-semibold text-slate-300">장바구니 & 결제 활성화</span>
                </div>
                <input
                  type="checkbox"
                  checked={enableCheckout}
                  onChange={(e) => setEnableCheckout(e.target.checked)}
                  className="w-4 h-4 rounded border-slate-800 text-blue-600 bg-slate-900"
                />
              </label>

              {/* Feature: Lookbook */}
              <label className="flex items-center justify-between p-3 bg-slate-950 border border-slate-800 rounded-lg cursor-pointer hover:border-slate-700 transition">
                <div className="flex items-center gap-2">
                  <BookOpen size={14} className="text-teal-400" />
                  <span className="text-xs font-semibold text-slate-300">AI 테마 룩북 활성화</span>
                </div>
                <input
                  type="checkbox"
                  checked={enableLookbook}
                  onChange={(e) => setEnableLookbook(e.target.checked)}
                  className="w-4 h-4 rounded border-slate-800 text-blue-600 bg-slate-900"
                />
              </label>

              {/* Feature: Reviews */}
              <label className="flex items-center justify-between p-3 bg-slate-950 border border-slate-800 rounded-lg cursor-pointer hover:border-slate-700 transition">
                <div className="flex items-center gap-2">
                  <MessageSquare size={14} className="text-amber-400" />
                  <span className="text-xs font-semibold text-slate-300">게시판 & 리뷰 활성화</span>
                </div>
                <input
                  type="checkbox"
                  checked={enableReviews}
                  onChange={(e) => setEnableReviews(e.target.checked)}
                  className="w-4 h-4 rounded border-slate-800 text-blue-600 bg-slate-900"
                />
              </label>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center justify-end gap-3 border-t border-slate-800 pt-4">
            <button
              type="button"
              onClick={fetchTenantTheme}
              className="bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white px-4 py-2 rounded-lg text-xs font-semibold transition"
            >
              되돌리기
            </button>
            <button
              type="submit"
              disabled={saveLoading}
              className="bg-blue-600 hover:bg-blue-500 disabled:bg-blue-800 text-white px-6 py-2 rounded-lg text-xs font-semibold transition shadow-lg shadow-blue-500/10 flex items-center gap-1.5"
            >
              {saveLoading ? (
                <>
                  <RefreshCw className="animate-spin" size={14} /> 저장 중...
                </>
              ) : (
                <>
                  <Check size={14} /> 적용하기
                </>
              )}
            </button>
          </div>
        </form>

        {/* RIGHT: Live Interactive Preview */}
        <div className="lg:col-span-5 space-y-4">
          <div className="sticky top-6">
            <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-2xl">
              <div className="bg-slate-800 border-b border-slate-700 px-4 py-3 flex items-center justify-between">
                <span className="text-xs font-bold text-slate-300 flex items-center gap-1.5">
                  <Eye size={14} className="text-emerald-400" /> 실시간 쇼핑몰 프리뷰 (Live Miniature Preview)
                </span>
                <span className="text-[10px] bg-slate-950 text-slate-500 px-2 py-0.5 rounded font-mono">
                  {fontFamily} Font
                </span>
              </div>

              {/* Preview Body Canvas */}
              <div 
                className="p-6 transition-colors duration-300 overflow-y-auto max-h-[640px]"
                style={{ backgroundColor: backgroundColor, fontFamily: fontFamily }}
              >
                {/* 0. Promo Strip Preview */}
                {enablePromo && (
                  <div 
                    className="-mx-6 -mt-6 mb-4 text-[8px] font-bold py-1 px-4 text-center flex items-center justify-center gap-1.5 transition-all"
                    style={{ backgroundColor: promoBgColor, color: promoTextColor }}
                  >
                    <span className="truncate">{promoText || "홍보 문구를 입력하세요"}</span>
                  </div>
                )}

                {/* 1. Header Mini Area */}
                <div className="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800 mb-4 text-[10px]">
                  <span className="font-black tracking-wider text-slate-800 dark:text-white uppercase flex items-center gap-1">
                    {logoUrl ? (
                      <img src={logoUrl} alt="Logo" className="h-4 max-w-[80px] object-contain bg-white/20 p-0.5 rounded" />
                    ) : (
                      <>
                        <span 
                          className="w-2.5 h-2.5 rounded-full inline-block animate-pulse" 
                          style={{ backgroundColor: primaryColor }}
                        />
                        {shopName || "LUX AI"}
                      </>
                    )}
                  </span>
                  <div className="flex gap-2 text-slate-400 dark:text-slate-500 font-medium">
                    <span>SHOP</span>
                    <span>AI FIT</span>
                    <span>MY</span>
                  </div>
                </div>

                {/* 2. Banner Preview */}
                {bannerMode === "image_only" ? (
                  <div 
                    className="relative rounded-lg overflow-hidden flex flex-col justify-end min-h-[140px] text-white transition-all duration-300 bg-cover bg-center border border-slate-200 dark:border-slate-800"
                    style={{
                      backgroundImage: bannerImageOnlyUrl ? `url(${bannerImageOnlyUrl})` : `linear-gradient(135deg, ${primaryColor}, ${secondaryColor})`
                    }}
                  >
                    {!bannerImageOnlyUrl && (
                      <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-950/60 p-4">
                        <ImageIcon size={20} className="text-slate-400 mb-1" />
                        <span className="text-[8px] text-slate-400">배너 사진 없음</span>
                      </div>
                    )}
                    {bannerImageOnlyUrl && (
                      <div className="absolute bottom-2 right-2 bg-black/60 backdrop-blur-sm px-2 py-0.5 rounded text-[8px] font-bold text-white flex items-center gap-1 z-10 border border-white/10">
                        <span>연결 링크 &rarr;</span>
                      </div>
                    )}
                  </div>
                ) : (
                  <div 
                    className={`relative p-5 rounded-lg overflow-hidden flex flex-col justify-center min-h-[140px] text-white transition-all duration-300 ${
                      bannerBgUrl ? 'bg-cover bg-center' : 'bg-gradient-to-br'
                    }`}
                    style={{
                      backgroundImage: bannerBgUrl ? `url(${bannerBgUrl})` : `linear-gradient(135deg, ${primaryColor}, ${secondaryColor})`
                    }}
                  >
                    {/* Overlay if image present */}
                    {bannerBgUrl && <div className="absolute inset-0 bg-black/40 z-0" />}
                    
                    <div className="relative z-10 space-y-1">
                      <h4 className="text-sm font-extrabold tracking-tight drop-shadow-md">
                        {bannerTitle || "배너 대제목을 입력하세요"}
                      </h4>
                      <p className="text-[9px] text-white/80 drop-shadow-sm leading-normal">
                        {bannerSubtitle || "배너 소제목을 입력하세요"}
                      </p>
                      <button 
                        type="button"
                        className={`mt-2 px-2.5 py-1 text-[8px] font-bold text-white transition-transform duration-200 self-start ${getRadiusClass(borderRadius)}`}
                        style={{ backgroundColor: primaryColor }}
                      >
                        쇼핑하기 &rarr;
                      </button>
                    </div>
                  </div>
                )}

                {/* 3. AI Feature Flags Indicators */}
                <div className="my-4 flex flex-wrap gap-1">
                  {enableVton && (
                    <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20 rounded text-[8px] font-bold">
                      <Sparkles size={8} /> 가상피팅 ON
                    </span>
                  )}
                  {enableLookbook && (
                    <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 bg-teal-500/10 text-teal-600 dark:text-teal-400 border border-teal-500/20 rounded text-[8px] font-bold">
                      <BookOpen size={8} /> AI코디 ON
                    </span>
                  )}
                  {enableCheckout && (
                    <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20 rounded text-[8px] font-bold">
                      <ShoppingCart size={8} /> 주문/결제 ON
                    </span>
                  )}
                  {enableReviews && (
                    <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 rounded text-[8px] font-bold">
                      <MessageSquare size={8} /> 구매후기 ON
                    </span>
                  )}
                </div>

                {/* 4. Product List Miniature Grid */}
                <div className="space-y-2 pt-2">
                  <div className="flex justify-between items-center text-[9px] text-slate-500 font-semibold mb-1">
                    <span>트렌디 베스트 상품</span>
                    <span>더보기 &gt;</span>
                  </div>

                  <div 
                    className={`grid gap-2.5 transition-all duration-300 ${
                      gridCols === 2 ? "grid-cols-2" : gridCols === 4 ? "grid-cols-4" : "grid-cols-3"
                    }`}
                  >
                    {[1, 2, 3, 4].slice(0, gridCols === 2 ? 2 : gridCols === 4 ? 4 : 3).map((item) => (
                      <div 
                        key={item} 
                        className={`bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700/60 p-1.5 transition-all shadow-sm overflow-hidden flex flex-col justify-between ${getRadiusClass(borderRadius)}`}
                      >
                        <div className="w-full aspect-[4/5] bg-slate-100 dark:bg-slate-700 rounded-sm mb-1.5 relative overflow-hidden flex items-center justify-center">
                          <span className="text-[7px] text-slate-400">PRODUCT {item}</span>
                          {enableVton && (
                            <span 
                              className="absolute top-1 right-1 p-0.5 rounded-full text-white cursor-pointer hover:scale-105 transition"
                              style={{ backgroundColor: primaryColor }}
                              title="피팅룸"
                            >
                              <Sparkles size={8} />
                            </span>
                          )}
                        </div>
                        <div className="space-y-0.5 text-[8px]">
                          <div className="font-bold text-slate-700 dark:text-slate-200 truncate">슬림핏 코튼 자켓</div>
                          <div className="text-slate-400 line-through text-[7px]">89,000원</div>
                          <div className="font-black text-slate-800 dark:text-white" style={{ color: primaryColor }}>59,000원</div>
                        </div>
                        {enableCheckout && (
                          <button 
                            type="button"
                            className="mt-1.5 w-full py-0.5 bg-slate-900 dark:bg-slate-700 text-white rounded text-[7px] font-medium"
                          >
                            담기
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                {/* 4.5 Promo Card Banner Preview */}
                <div className="mt-6 pt-2">
                  <div 
                    className="relative rounded-lg overflow-hidden flex flex-col justify-center min-h-[120px] text-white transition-all duration-300 bg-cover bg-center border border-slate-200 dark:border-slate-800"
                    style={{
                      backgroundImage: promoCardImgUrl ? `url(${promoCardImgUrl})` : `linear-gradient(135deg, ${primaryColor}, ${secondaryColor})`
                    }}
                  >
                    <div className="absolute inset-0 bg-black/40 z-0" />
                    <div className="relative z-10 p-3.5 space-y-1">
                      <h5 className="text-[10px] font-extrabold tracking-tight drop-shadow-md">
                        {promoCardTitle || "프로모션 타이틀"}
                      </h5>
                      <p className="text-[7px] text-white/80 drop-shadow-sm leading-normal max-w-[80%] whitespace-pre-wrap">
                        {promoCardDesc || "프로모션 설명글"}
                      </p>
                      {promoCardLinkUrl && (
                        <span className="inline-block mt-1 text-[6px] font-bold opacity-95 underline">
                          기획전 보러가기 &rarr;
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* 5. Footer Preview */}
                <div className="mt-6 -mx-6 -mb-6 bg-slate-50 dark:bg-slate-900 border-t border-slate-200 dark:border-slate-850 p-4 text-[7px] text-slate-500 dark:text-slate-400 space-y-2">
                  <div className="flex justify-between items-center border-b border-slate-200 dark:border-slate-800 pb-1.5">
                    <span className="font-bold text-slate-700 dark:text-slate-350">{footerCompany || "회사명"}</span>
                    <span>대표자: {footerOwner || "대표자"}</span>
                  </div>
                  <div className="space-y-0.5 leading-relaxed opacity-80">
                    <div>주소: {footerAddress || "회사 주소"}</div>
                    <div className="flex gap-2">
                      <span>Tel: {footerTel || "전화번호"}</span>
                      <span>Email: {footerEmail || "이메일"}</span>
                    </div>
                    <div className="flex gap-2">
                      <span>사업자등록번호: {footerBizNum || "사업자번호"}</span>
                      <span>통신판매신고: {footerReportNum || "신고번호"}</span>
                    </div>
                  </div>
                  <div className="text-[6px] text-slate-400 dark:text-slate-600 pt-1">
                    {footerCopyright || `© 2026 ${shopName || "LUX AI"}. All rights reserved.`}
                  </div>
                </div>

              </div>
            </div>
            
            {/* Guide Card */}
            <div className="bg-slate-900/50 border border-slate-800/80 p-4 rounded-xl mt-4 space-y-2">
              <span className="text-xs font-semibold text-slate-300 flex items-center gap-1">
                <HelpCircle size={14} className="text-blue-400" /> 디자인 가이드 팁
              </span>
              <p className="text-[10px] text-slate-400 leading-normal">
                메인 배너의 이미지 URL을 비우시면 기본적으로 <strong>메인 컬러와 보조 컬러 간의 세련된 그라데이션</strong>이 적용되어 더욱 트렌디하고 화려한 첫인상을 제공합니다.
              </p>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
