"use client";

import { usePathname } from "next/navigation";
import Navigation from "@/components/Navigation";
import Footer from "@/components/Footer";
import SupportWidget from "@/components/SupportWidget";

export function LayoutWrapper({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isAdmin = pathname?.startsWith("/admin");

  if (isAdmin) {
    return (
      <main className="flex-grow">
        {children}
      </main>
    );
  }

  return (
    <>
      <Navigation />
      <main className="flex-grow pt-20">
        {children}
      </main>
      <Footer />
      <SupportWidget />
    </>
  );
}
