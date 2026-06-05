"use client";

import { Camera, Plus, Loader2 } from "lucide-react";

export default function AIStudioPage() {
  return (
    <div className="bg-white dark:bg-slate-800 rounded-3xl shadow-sm border border-slate-200/60 dark:border-slate-700/50 overflow-hidden min-h-[600px] flex flex-col">
      <div className="p-8 sm:p-10 border-b border-slate-100 dark:border-slate-700">
        <div className="flex justify-between items-center">
          <div className="flex items-center space-x-3">
            <div className="bg-fuchsia-100 dark:bg-fuchsia-900/40 p-2.5 rounded-lg text-fuchsia-600 dark:text-fuchsia-400">
              <Camera size={24} />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-900 dark:text-white">AI Fitting Studio</h1>
              <p className="text-sm text-slate-500 mt-1">내 가상의 AI 모델로 다채로운 피팅을 구성해보세요.</p>
            </div>
          </div>
          <button className="hidden sm:flex items-center px-5 py-2.5 bg-slate-900 dark:bg-white text-white dark:text-slate-900 font-bold rounded-xl hover:scale-105 transition-transform shadow-lg">
            <Plus size={18} className="mr-2" /> 새 피팅 구성
          </button>
        </div>
      </div>

      <div className="flex-1 flex flex-col items-center justify-center p-10 text-center relative overflow-hidden">
        {/* Decorative BG Elements */}
        <div className="absolute inset-0 flex items-center justify-center opacity-5 pointer-events-none">
          <div className="w-[500px] h-[500px] border border-fuchsia-500 rounded-full"></div>
          <div className="absolute w-[300px] h-[300px] border border-blue-500 rounded-full"></div>
        </div>

        <div className="relative z-10 p-8 rounded-3xl bg-white/50 dark:bg-slate-800/50 backdrop-blur-xl border border-white/20 dark:border-slate-700 shadow-2xl max-w-md">
          <div className="w-20 h-20 bg-gradient-to-br from-fuchsia-500 to-purple-600 rounded-2xl flex items-center justify-center text-white shadow-xl mx-auto mb-6 transform -rotate-6">
            <Camera size={36} />
          </div>
          <h2 className="text-xl font-black text-slate-900 dark:text-white mb-2">진행 중인 피팅 프로젝트가 없습니다</h2>
          <p className="text-sm text-slate-500 leading-relaxed font-medium mb-8">
            상품 상세 페이지에서 <b>[내 AI 모델로 피팅하기]</b> 버튼을 클릭하시면, 내가 선택한 상품을 핏과 각도에 맞게 생성할 수 있습니다.
          </p>
          <button className="w-full py-3.5 bg-gradient-to-r from-blue-600 to-fuchsia-600 text-white font-bold rounded-xl flex items-center justify-center hover:opacity-90 transition-opacity shadow-lg shadow-purple-500/20">
            상품 둘러보러 가기
          </button>
        </div>
      </div>
    </div>
  );
}
