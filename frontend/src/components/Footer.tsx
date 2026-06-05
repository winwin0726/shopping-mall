"use client";

import React from "react";
import Link from "next/link";
import { useTheme } from "./ThemeProvider";
import { ShieldCheck, Mail, Phone, MapPin, Award } from "lucide-react";

export default function Footer() {
  const { themeConfig, tenantName } = useTheme();

  // 안전한 폴백을 위한 기본값 매핑
  const company = themeConfig.footerCompany || "LUXAI 주식회사";
  const owner = themeConfig.footerOwner || "홍길동";
  const address = themeConfig.footerAddress || "서울특별시 강남구 테헤란로 123 LUXAI 타워 15층";
  const tel = themeConfig.footerTel || "1644-1234";
  const email = themeConfig.footerEmail || "support@luxai.com";
  const bizNum = themeConfig.footerBizNum || "120-81-12345";
  const reportNum = themeConfig.footerReportNum || "제 2026-서울강남-1234호";
  const copyright = themeConfig.footerCopyright || `© 2026 ${tenantName}. ALL RIGHTS RESERVED.`;

  return (
    <footer className="bg-slate-900 text-slate-400 dark:bg-slate-950 border-t border-slate-800 pt-16 pb-8 transition-colors duration-300">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        
        {/* Top Info Grid */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8 pb-12 border-b border-slate-800">
          
          {/* Logo & Slogan */}
          <div className="space-y-4 md:col-span-2">
            <h3 className="text-xl font-black tracking-tight text-white uppercase flex items-center gap-2">
              <Award className="text-blue-500" size={20} />
              {tenantName}
            </h3>
            <p className="text-sm text-slate-400 max-w-sm font-medium leading-relaxed">
              개인 맞춤형 가상 피팅 룸 솔루션. 옷의 실시간 핏을 마네킹 캔버스 및 AI 비전 매핑으로 완벽하게 확인해 보세요.
            </p>
          </div>

          {/* Quick Menu */}
          <div>
            <h4 className="text-sm font-bold text-white uppercase tracking-wider mb-4">고객 만족 센터</h4>
            <ul className="space-y-2 text-sm font-medium">
              <li className="flex items-center gap-2">
                <Phone size={14} className="text-blue-500" />
                <span>{tel} (평일 10:00 - 17:00)</span>
              </li>
              <li className="flex items-center gap-2">
                <Mail size={14} className="text-blue-500" />
                <a href={`mailto:${email}`} className="hover:text-white transition">{email}</a>
              </li>
              <li className="flex items-center gap-2">
                <ShieldCheck size={14} className="text-blue-500" />
                <Link href="/mypage/support" className="hover:text-white transition">1:1 고객 문의하기</Link>
              </li>
            </ul>
          </div>

          {/* Business Info Header */}
          <div>
            <h4 className="text-sm font-bold text-white uppercase tracking-wider mb-4">서비스 정책</h4>
            <div className="flex flex-wrap gap-x-4 gap-y-2 text-sm font-medium">
              <a href="#" className="hover:text-white transition">이용약관</a>
              <a href="#" className="hover:text-white transition font-bold text-blue-400">개인정보처리방침</a>
              <a href="#" className="hover:text-white transition">에스크로 구매안전</a>
            </div>
          </div>
        </div>

        {/* Bottom Details (Business Registration) */}
        <div className="pt-8 flex flex-col md:flex-row justify-between items-start md:items-center gap-6 text-xs text-slate-500 font-medium">
          <div className="space-y-2 max-w-4xl leading-relaxed">
            <p className="flex flex-wrap gap-x-4 gap-y-1">
              <span><strong>상호명:</strong> {company}</span>
              <span><strong>대표자:</strong> {owner}</span>
              <span><strong>사업자등록번호:</strong> {bizNum}</span>
              <span><strong>통신판매업신고:</strong> {reportNum}</span>
            </p>
            <p className="flex items-center gap-1">
              <MapPin size={12} className="shrink-0 text-slate-600" />
              <span><strong>사업장 소재지:</strong> {address}</span>
            </p>
          </div>
          <div className="shrink-0 text-slate-500 font-semibold tracking-tight text-center md:text-right">
            {copyright}
          </div>
        </div>
      </div>
    </footer>
  );
}
