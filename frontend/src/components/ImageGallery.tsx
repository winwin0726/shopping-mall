"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronLeft, ChevronRight, ZoomIn, X, Play } from "lucide-react";

interface ImageGalleryProps {
  images: string[];
  productName: string;
  videoUrl?: string;
}

export default function ImageGallery({ images, productName, videoUrl }: ImageGalleryProps) {
  const [activeIndex, setActiveIndex] = useState(0);
  const [isZoomed, setIsZoomed] = useState(false);

  // 이미지 및 동영상을 아우르는 통합 미디어 아이템 리스트 조립
  const mediaItems: { type: "image" | "video"; url: string }[] = [];
  
  if (videoUrl) {
    mediaItems.push({ type: "video", url: videoUrl });
  }
  
  const displayImages = images && images.length > 0
    ? images
    : ["https://cdn-icons-png.flaticon.com/512/863/863684.png"];
    
  displayImages.forEach(img => {
    mediaItems.push({ type: "image", url: img });
  });

  const goTo = (index: number) => {
    if (index < 0) setActiveIndex(mediaItems.length - 1);
    else if (index >= mediaItems.length) setActiveIndex(0);
    else setActiveIndex(index);
  };

  const getYoutubeEmbedUrl = (url: string) => {
    let videoId = "";
    if (url.includes("youtube.com/watch")) {
      const urlParams = new URLSearchParams(url.split("?")[1]);
      videoId = urlParams.get("v") || "";
    } else if (url.includes("youtu.be/")) {
      videoId = url.split("youtu.be/")[1]?.split("?")[0] || "";
    } else if (url.includes("youtube.com/embed/")) {
      videoId = url.split("youtube.com/embed/")[1]?.split("?")[0] || "";
    }
    return videoId ? `https://www.youtube.com/embed/${videoId}?autoplay=1&mute=1` : url;
  };

  const isYoutubeVideo = (url: string) => {
    return url.includes("youtube.com") || url.includes("youtu.be");
  };

  const currentMedia = mediaItems[activeIndex];

  return (
    <div className="flex flex-col gap-4">
      {/* 메인 미디어 영역 */}
      <div className="relative group aspect-[4/5] w-full bg-white dark:bg-slate-800 rounded-3xl overflow-hidden border border-slate-200 dark:border-slate-700 shadow-lg flex items-center justify-center">
        <AnimatePresence mode="wait">
          {currentMedia.type === "video" ? (
            <motion.div
              key={`video-${activeIndex}`}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="w-full h-full relative"
            >
              {isYoutubeVideo(currentMedia.url) ? (
                <iframe
                  src={getYoutubeEmbedUrl(currentMedia.url)}
                  title={`${productName} - 동영상`}
                  className="w-full h-full border-none"
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                  allowFullScreen
                />
              ) : (
                <video
                  src={currentMedia.url}
                  controls
                  autoPlay
                  muted
                  className="w-full h-full object-contain p-2"
                />
              )}
            </motion.div>
          ) : (
            <motion.img
              key={`img-${activeIndex}`}
              src={currentMedia.url}
              alt={`${productName} - 이미지`}
              initial={{ opacity: 0, scale: 1.02 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.98 }}
              transition={{ duration: 0.3 }}
              className="w-full h-full object-contain p-4 cursor-zoom-in"
              onClick={() => setIsZoomed(true)}
            />
          )}
        </AnimatePresence>

        {/* 좌우 네비게이션 */}
        {mediaItems.length > 1 && (
          <>
            <button
              onClick={() => goTo(activeIndex - 1)}
              className="absolute left-3 top-1/2 -translate-y-1/2 w-10 h-10 bg-white/80 dark:bg-slate-900/80 backdrop-blur-sm rounded-full flex items-center justify-center shadow-md opacity-0 group-hover:opacity-100 transition-opacity hover:scale-110 z-10"
              aria-label="이전 미디어"
            >
              <ChevronLeft size={20} />
            </button>
            <button
              onClick={() => goTo(activeIndex + 1)}
              className="absolute right-3 top-1/2 -translate-y-1/2 w-10 h-10 bg-white/80 dark:bg-slate-900/80 backdrop-blur-sm rounded-full flex items-center justify-center shadow-md opacity-0 group-hover:opacity-100 transition-opacity hover:scale-110 z-10"
              aria-label="다음 미디어"
            >
              <ChevronRight size={20} />
            </button>
          </>
        )}

        {/* 줌 버튼 (이미지인 경우에만 노출) */}
        {currentMedia.type === "image" && (
          <button
            onClick={() => setIsZoomed(true)}
            className="absolute right-3 bottom-3 w-10 h-10 bg-white/80 dark:bg-slate-900/80 backdrop-blur-sm rounded-full flex items-center justify-center shadow-md opacity-0 group-hover:opacity-100 transition-opacity hover:scale-110 z-10"
            aria-label="이미지 확대"
          >
            <ZoomIn size={18} />
          </button>
        )}

        {/* 페이지 인디케이터 */}
        {mediaItems.length > 1 && (
          <div className="absolute bottom-3 left-1/2 -translate-x-1/2 flex gap-1.5 z-10 bg-black/35 px-2.5 py-1.5 rounded-full backdrop-blur-sm border border-white/5">
            {mediaItems.map((_, i) => (
              <button
                key={i}
                onClick={() => setActiveIndex(i)}
                className={`w-2 h-2 rounded-full transition-all ${
                  i === activeIndex
                    ? "bg-blue-500 w-4"
                    : "bg-slate-400/50 hover:bg-slate-400"
                }`}
              />
            ))}
          </div>
        )}
      </div>

      {/* 썸네일 리스트 (미디어가 2개 이상일 때만) */}
      {mediaItems.length > 1 && (
        <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-thin">
          {mediaItems.map((item, i) => (
            <button
              key={i}
              onClick={() => setActiveIndex(i)}
              className={`flex-shrink-0 w-16 h-20 md:w-20 md:h-24 rounded-xl overflow-hidden border-2 transition-all relative ${
                i === activeIndex
                  ? "border-blue-500 shadow-md shadow-blue-500/20 ring-2 ring-blue-500/30"
                  : "border-slate-200 dark:border-slate-700 hover:border-blue-300 opacity-60 hover:opacity-100"
              }`}
            >
              {item.type === "video" ? (
                <div className="w-full h-full bg-slate-950 flex flex-col items-center justify-center text-slate-400">
                  <Play size={20} className="text-blue-500" fill="currentColor" />
                  <span className="text-[8px] font-bold text-slate-500 uppercase mt-1">VIDEO</span>
                </div>
              ) : (
                <img
                  src={item.url}
                  alt={`썸네일 ${i + 1}`}
                  className="w-full h-full object-cover"
                />
              )}
            </button>
          ))}
        </div>
      )}

      {/* 풀스크린 줌 모달 */}
      <AnimatePresence>
        {isZoomed && currentMedia.type === "image" && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] bg-black/90 backdrop-blur-md flex items-center justify-center cursor-zoom-out"
            onClick={() => setIsZoomed(false)}
          >
            <motion.img
              initial={{ scale: 0.8 }}
              animate={{ scale: 1 }}
              exit={{ scale: 0.8 }}
              src={currentMedia.url}
              alt={productName}
              className="max-w-[90vw] max-h-[90vh] object-contain rounded-xl shadow-2xl"
            />
            <button
              onClick={() => setIsZoomed(false)}
              className="absolute top-6 right-6 w-12 h-12 bg-white/10 backdrop-blur-sm rounded-full flex items-center justify-center text-white hover:bg-white/20 transition animate-in fade-in"
            >
              <X size={20} />
            </button>
            
            {/* 줌 모달 내 좌우 네비게이션 */}
            {mediaItems.length > 1 && (
              <>
                <button
                  onClick={(e) => { e.stopPropagation(); goTo(activeIndex - 1); }}
                  className="absolute left-6 top-1/2 -translate-y-1/2 w-12 h-12 bg-white/10 backdrop-blur-sm rounded-full flex items-center justify-center text-white hover:bg-white/20 transition"
                >
                  <ChevronLeft size={24} />
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); goTo(activeIndex + 1); }}
                  className="absolute right-6 top-1/2 -translate-y-1/2 w-12 h-12 bg-white/10 backdrop-blur-sm rounded-full flex items-center justify-center text-white hover:bg-white/20 transition"
                >
                  <ChevronRight size={24} />
                </button>
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
