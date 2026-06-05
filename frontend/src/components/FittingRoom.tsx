"use client";

export interface OutfitState {
  top: string | null;
  bottom: string | null;
  accessory: string | null;
}

interface FittingRoomProps {
  outfit: OutfitState;
  onReset?: () => void;
}

export default function FittingRoom({ outfit, onReset }: FittingRoomProps) {
  return (
    <div className="w-full max-w-md mx-auto aspect-[3/4] bg-white dark:bg-slate-900 rounded-xl overflow-hidden relative border border-slate-200 dark:border-slate-700">
      <div className="absolute inset-0 flex items-center justify-center text-slate-300">
        <span className="text-6xl">👤</span>
      </div>
      {outfit.top && (
        <img src={outfit.top} alt="Top" className="absolute inset-0 w-full h-full object-contain z-10" />
      )}
      {outfit.bottom && (
        <img src={outfit.bottom} alt="Bottom" className="absolute inset-0 w-full h-full object-contain z-20" />
      )}
      {outfit.accessory && (
        <img src={outfit.accessory} alt="Accessory" className="absolute inset-0 w-full h-full object-contain z-30" />
      )}
      {onReset && (outfit.top || outfit.bottom || outfit.accessory) && (
        <button
          onClick={onReset}
          className="absolute bottom-4 right-4 z-40 px-4 py-2 bg-red-500 text-white text-xs font-bold rounded-lg shadow hover:bg-red-600 transition"
        >
          Reset
        </button>
      )}
    </div>
  );
}