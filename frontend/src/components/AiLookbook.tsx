"use client";

import { OutfitState } from "./FittingRoom";
import Image from "next/image";

interface AiLookbookProps {
  outfit: OutfitState;
  premiumDocs: number;
  onPremiumClick: () => void;
}

export default function AiLookbook({ outfit, premiumDocs, onPremiumClick }: AiLookbookProps) {
  const hasOutfit = outfit.top || outfit.bottom || outfit.accessory;

  return (
    <section id="ai-lookbook" className="py-24 bg-slate-50 dark:bg-slate-800/50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <span className="uppercase tracking-[0.2em] text-xs font-bold text-blue-600 mb-2 block">
            Virtual Try-On
          </span>
          <h2 className="text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">
            AI Fitting Room
          </h2>
          <p className="text-slate-500 mt-3 font-medium max-w-md mx-auto">
            상품을 선택하면 AI가 자동으로 코디를 완성합니다
          </p>
        </div>

        <div className="flex flex-col lg:flex-row items-center gap-12">
          {/* Canvas */}
          <div className="w-full max-w-md aspect-[3/4] bg-white dark:bg-slate-900 rounded-3xl shadow-2xl p-6 relative border border-slate-200 dark:border-slate-800 overflow-hidden flex flex-col justify-between">
            <div className="absolute top-4 left-4 flex gap-2 z-10">
               <span className="w-3 h-3 rounded-full bg-red-400"></span>
               <span className="w-3 h-3 rounded-full bg-amber-400"></span>
               <span className="w-3 h-3 rounded-full bg-emerald-400"></span>
            </div>
            {hasOutfit ? (
              <div className="w-full h-full relative rounded-2xl flex flex-col pt-8">
                {outfit.top && (
                  <div className="flex-1 flex items-center justify-center relative">
                    <Image src={outfit.top} alt="top" width={250} height={300} className="object-contain drop-shadow-xl" />
                  </div>
                )}
                {outfit.bottom && (
                  <div className="flex-1 flex items-center justify-center relative">
                    <Image src={outfit.bottom} alt="bottom" width={250} height={300} className="object-contain drop-shadow-xl" />
                  </div>
                )}
              </div>
            ) : (
              <div className="w-full h-full flex flex-col items-center justify-center text-slate-400 gap-6">
                <div className="relative w-32 h-32">
                   <div className="absolute inset-0 bg-blue-100 dark:bg-slate-800 rounded-full animate-ping opacity-50"></div>
                   <div className="relative w-full h-full bg-blue-50 dark:bg-slate-800 rounded-full flex items-center justify-center shadow-inner border-2 border-slate-200 dark:border-slate-700">
                     <span className="text-5xl opacity-80">👕</span>
                   </div>
                </div>
                <div className="text-center">
                  <h3 className="text-xl font-bold text-slate-800 dark:text-white">가상 피팅룸 준비 완료</h3>
                  <p className="text-sm mt-2">왼쪽 상품 목록에서 입어볼 옷을 선택하세요.</p>
                  <p className="text-xs text-blue-500 font-semibold mt-4">AI Vision 모델 대기 중...</p>
                </div>
              </div>
            )}
            
            {/* 하단 스캐너 애니메이션 효과 */}
            {!hasOutfit && (
              <div className="absolute bottom-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-blue-500 to-transparent opacity-50 shadow-[0_0_10px_#3b82f6]"></div>
            )}
          </div>

          {/* Info */}
          <div className="flex-1 text-center lg:text-left">
            <h3 className="text-2xl font-bold text-slate-900 dark:text-white mb-4">
              Premium AI 가상 피팅
            </h3>
            <p className="text-slate-600 dark:text-slate-400 mb-6 leading-relaxed">
              단순한 레이어 합성이 아닌, 딥러닝 기반 의류 변형 기술을 활용한 고품질 가상 피팅 서비스입니다.
              내 체형에 맞게 자연스럽게 옷이 변형됩니다.
            </p>
            <div className="flex items-center gap-4 justify-center lg:justify-start mb-6">
              <span className="text-sm font-bold text-slate-500">남은 무료 이용권:</span>
              <span className="text-2xl font-black text-blue-600">{premiumDocs}회</span>
            </div>
            <button
              onClick={onPremiumClick}
              className="px-8 py-4 bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-bold rounded-xl hover:from-blue-700 hover:to-indigo-700 transition shadow-lg"
            >
              🚀 Premium 가상 피팅 체험하기
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}