"use client";
import { authFetch, API_URL } from "@/lib/api";

import React, { useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { Edit3, Check, X, Loader2 } from "lucide-react";

interface InlineProductEditorProps {
  productId: number;
  fieldName: "kr_name" | "base_price" | "sale_price";
  initialValue: string | number;
  onSuccess?: (newValue: any) => void;
  className?: string;
  style?: React.CSSProperties;
  children: React.ReactNode;
}

export default function InlineProductEditor({
  productId,
  fieldName,
  initialValue,
  onSuccess,
  className = "",
  style,
  children
}: InlineProductEditorProps) {
  const { user } = useAuth();
  const [isEditing, setIsEditing] = useState(false);
  const [value, setValue] = useState<string>(String(initialValue));
  const [loading, setLoading] = useState(false);

  const isAdmin = user && user.role === "ADMIN";

  if (!isAdmin) {
    return <span className={className} style={style}>{children}</span>;
  }

  const handleSave = async () => {
    const trimmed = value.trim();
    if (!trimmed) return;
    
    setLoading(true);
    try {
      const apiUrl = API_URL;
      const token = localStorage.getItem("token");
      
      const payload: any = {};
      if (fieldName === "base_price" || fieldName === "sale_price") {
        payload[fieldName] = parseInt(trimmed) || 0;
      } else {
        payload[fieldName] = trimmed;
      }

      const res = await authFetch(`${apiUrl}/api/admin/products/${productId}/inline-update`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify(payload)
      });

      if (!res.ok) throw new Error("현장 수정에 실패했습니다.");
      
      setIsEditing(false);
      if (onSuccess) {
        onSuccess(payload[fieldName]);
      } else {
        // 전역 상태가 아니면 간단하게 새로고침 처리 하거나 화면 갱신
        window.location.reload();
      }
    } catch (err: any) {
      alert(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <span 
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        setIsEditing(true);
      }}
      className={`group/inline relative inline-block cursor-pointer border border-transparent hover:border-dashed hover:border-blue-500/80 rounded px-1.5 -mx-1.5 transition-all ${
        isEditing ? "z-50 bg-slate-900 border border-blue-500 p-1" : ""
      } ${className}`}
      style={style}
      title="관리자: 즉석 실시간 수정"
    >
      {isEditing ? (
        <span className="inline-flex items-center gap-1" onClick={e => e.stopPropagation()}>
          <input
            type={fieldName.includes("price") ? "number" : "text"}
            value={value}
            onChange={e => setValue(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleSave()}
            className="bg-slate-950 border border-slate-700 text-xs px-2 py-0.5 text-white rounded focus:outline-none focus:border-blue-500 font-sans max-w-[120px]"
            disabled={loading}
            autoFocus
          />
          {loading ? (
            <Loader2 size={12} className="animate-spin text-blue-400 shrink-0" />
          ) : (
            <span className="flex gap-0.5 shrink-0">
              <button 
                onClick={handleSave}
                className="p-0.5 bg-blue-600 hover:bg-blue-500 text-white rounded"
                title="저장"
              >
                <Check size={10} />
              </button>
              <button 
                onClick={() => setIsEditing(false)}
                className="p-0.5 bg-slate-800 hover:bg-slate-750 text-slate-300 rounded"
                title="취소"
              >
                <X size={10} />
              </button>
            </span>
          )}
        </span>
      ) : (
        <>
          {children}
          <span className="absolute -top-3.5 right-0 bg-blue-600 text-white text-[8px] px-1 py-0.5 rounded shadow opacity-0 group-hover/inline:opacity-100 transition-opacity flex items-center gap-0.5 z-20 pointer-events-none whitespace-nowrap">
            <Edit3 size={8} /> 클릭 수정
          </span>
        </>
      )}
    </span>
  );
}
