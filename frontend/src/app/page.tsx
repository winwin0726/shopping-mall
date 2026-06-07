"use client";

import { useState, useEffect } from "react";
import { API_URL } from "@/lib/api";
import { OutfitState } from "@/components/FittingRoom";
import { Product } from "@/components/ProductList";
import PremiumVtonModal from "@/components/PremiumVtonModal";
import HeroBanner from "@/components/HeroBanner";
import CategoryPills from "@/components/CategoryPills";
import FeaturedProducts from "@/components/FeaturedProducts";
import PromoBanner from "@/components/PromoBanner";
import AiLookbook from "@/components/AiLookbook";
import { useTheme } from "@/components/ThemeProvider";

export default function Home() {
  const [outfit, setOutfit] = useState<OutfitState>({ top: null, bottom: null, accessory: null });
  const [premiumDocs, setPremiumDocs] = useState(3);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const { themeConfig } = useTheme();

  useEffect(() => {
    async function fetchProducts() {
      try {
        const apiUrl = API_URL;
        const response = await fetch(`${apiUrl}/api/products`);
        if (response.ok) {
          const data = await response.json();
          setProducts(data);
        }
      } catch (error) {
        console.warn("Failed to fetch products from backend:", error);
        setProducts([]);
      } finally {
        setLoading(false);
      }
    }
    fetchProducts();
  }, []);

  const handleSelectProduct = (product: Product) => {
    setOutfit(prev => ({
      ...prev,
      [product.category]: prev[product.category] === product.transparentImage ? null : product.transparentImage
    }));

    const element = document.getElementById('ai-lookbook');
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  };

  const handlePremiumClick = () => {
    setIsModalOpen(true);
  };

  const handleVtonComplete = () => {
    setPremiumDocs(prev => Math.max(0, prev - 1));
    setIsModalOpen(false);
    alert("AI 가상 피팅이 완료되었습니다! 결과를 확인해 보세요. (데모)");
  };

  const isVtonEnabled = themeConfig.features?.enable_vton !== false;
  const isLookbookEnabled = themeConfig.features?.enable_lookbook !== false;

  return (
    <div className="min-h-screen transition-colors duration-300" style={{ backgroundColor: themeConfig.backgroundColor }}>
      {/* 1. Hero Banner */}
      <HeroBanner />

      {/* 2. Quick Category Navigation */}
      <CategoryPills />

      {/* 3. Featured Products Grid */}
      <FeaturedProducts products={products} onTryOn={handleSelectProduct} />

      {/* 4. Promotional Banner */}
      <PromoBanner />

      {/* 5. AI Lookbook / Fitting Room Section */}
      {isLookbookEnabled && (
        <AiLookbook
          outfit={outfit}
          premiumDocs={premiumDocs}
          onPremiumClick={handlePremiumClick}
        />
      )}

      {/* Global Premium Vton Modal Overlay */}
      {isVtonEnabled && (
        <PremiumVtonModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          onComplete={handleVtonComplete}
        />
      )}
    </div>
  );
}