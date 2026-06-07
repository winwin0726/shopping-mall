"use client";

import { useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import { 
  MessageSquare, X, Send, Clock, CheckCircle2, Loader2, LogIn, HelpCircle, ArrowRight
} from "lucide-react";
import Link from "next/link";
import { useAuth } from "@/hooks/useAuth";

import { useTheme } from "@/components/ThemeProvider";

interface Ticket {
  id: number;
  subject: string;
  content: string;
  status: string;
  answer: string | null;
  answered_at: string | null;
  created_at: string;
}

export default function SupportWidget() {
  const apiUrl = API_URL;
  const { user } = useAuth();
  const { themeConfig, tenantName } = useTheme();
  
  const [mounted, setMounted] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<"write" | "list">("write");
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(false);
  
  // Form states
  const [subject, setSubject] = useState("");
  const [content, setContent] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Selected ticket detail view inside widget
  const [selectedTicket, setSelectedTicket] = useState<Ticket | null>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  const fetchTickets = async () => {
    const token = localStorage.getItem("token");
    if (!token) return;
    setLoading(true);
    try {
      const res = await fetch(`${apiUrl}/api/support/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        setTickets(await res.json());
      }
    } catch (err) {
      console.error("문의 내역 조회 실패:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen && user && mounted) {
      fetchTickets();
    }
  }, [isOpen, user, mounted]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!subject.trim() || !content.trim()) return;
    
    setSubmitting(true);
    const token = localStorage.getItem("token");
    try {
      const res = await fetch(`${apiUrl}/api/support/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ subject, content }),
      });
      if (res.ok) {
        setSubject("");
        setContent("");
        alert("1:1 문의가 정상적으로 접수되었습니다.");
        setActiveTab("list");
        fetchTickets();
      } else {
        alert("문의 접수에 실패했습니다. 잠시 후 다시 시도해주세요.");
      }
    } catch (err) {
      console.error(err);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed top-1/2 right-6 -translate-y-1/2 z-[9999] font-sans flex flex-col items-end gap-3">
      {/* Floating Circle Button */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="w-14 h-14 text-white rounded-full flex items-center justify-center shadow-2xl hover:scale-105 transition-all duration-300 relative group border border-white/10"
          style={{
            backgroundImage: `linear-gradient(135deg, ${themeConfig.primaryColor || '#2563eb'}, ${themeConfig.secondaryColor || '#4f46e5'})`
          }}
          title="1:1 고객 문의"
        >
          <MessageSquare size={24} className="animate-pulse" />
          <span className="absolute -top-1 -right-1 w-3 h-3 bg-red-500 rounded-full border-2 border-white dark:border-slate-900 hidden group-hover:block" />
        </button>
      )}

      {/* Slide-Up Chat Panel */}
      {isOpen && (
        <div className="bg-slate-900 border border-slate-800 w-80 sm:w-96 h-[500px] rounded-2xl shadow-2xl flex flex-col overflow-hidden animate-in slide-in-from-right-8 fade-in duration-300">
          {/* Header */}
          <div className="p-4 bg-gradient-to-r from-slate-900 to-slate-800 border-b border-slate-800 flex justify-between items-center shrink-0">
            <div className="flex items-center gap-2">
              <HelpCircle className="text-blue-500" size={20} style={{ color: themeConfig.primaryColor }} />
              <div>
                <h4 className="text-sm font-bold text-white leading-normal">{tenantName} 1:1 고객지원</h4>
                <p className="text-[10px] text-slate-400">궁금하신 사항을 남겨주시면 빠르게 답변해 드립니다.</p>
              </div>
            </div>
            <button 
              onClick={() => {
                setIsOpen(false);
                setSelectedTicket(null);
              }} 
              className="text-slate-400 hover:text-white bg-slate-800/60 p-1.5 rounded-lg transition"
            >
              <X size={16} />
            </button>
          </div>

          {/* User Status Content */}
          {!user ? (
            /* 비로그인 안내 화면 */
            <div className="flex-1 p-6 flex flex-col items-center justify-center text-center space-y-4">
              <div className="w-12 h-12 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-500">
                <LogIn size={20} />
              </div>
              <div className="space-y-1">
                <h5 className="text-sm font-bold text-slate-300">로그인이 필요한 서비스입니다</h5>
                <p className="text-xs text-slate-500 leading-normal">회원님의 1:1 문의 보호 및 정확한 매핑을 위해 로그인이 필수적입니다.</p>
              </div>
              <Link
                href="/login"
                onClick={() => setIsOpen(false)}
                className="w-full bg-blue-600 hover:bg-blue-500 text-white py-2 rounded-xl text-xs font-bold transition flex items-center justify-center gap-1 shadow-lg shadow-blue-500/10"
              >
                로그인하러 가기 <ArrowRight size={14} />
              </Link>
            </div>
          ) : selectedTicket ? (
            /* 문의 개별 상세 보기 화면 */
            <div className="flex-grow flex flex-col min-h-0">
              {/* Back Button */}
              <button 
                onClick={() => setSelectedTicket(null)} 
                className="px-4 py-2 text-xs font-bold text-blue-400 hover:text-blue-300 hover:underline text-left shrink-0 border-b border-slate-800"
              >
                &larr; 목록으로 돌아가기
              </button>
              
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {/* Subject & Created date */}
                <div>
                  <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[9px] font-bold border ${
                    selectedTicket.status === "ANSWERED"
                      ? "bg-green-500/10 text-green-400 border-green-500/20"
                      : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                  }`}>
                    {selectedTicket.status === "ANSWERED" ? "답변 완료" : "답변 대기"}
                  </span>
                  <h5 className="text-sm font-bold text-white mt-1.5 leading-snug">{selectedTicket.subject}</h5>
                </div>

                {/* My Question */}
                <div className="space-y-1">
                  <span className="text-[9px] font-bold text-slate-500 uppercase tracking-wider">나의 질문</span>
                  <div className="bg-slate-950 p-3 rounded-xl border border-slate-850 text-slate-300 text-xs whitespace-pre-wrap leading-relaxed">
                    {selectedTicket.content}
                  </div>
                  <div className="text-[9px] text-slate-500 text-right pr-1 font-mono">
                    {new Date(selectedTicket.created_at).toLocaleString("ko-KR")}
                  </div>
                </div>

                {/* Admin Reply */}
                {selectedTicket.answer ? (
                  <div className="space-y-1 pt-1">
                    <span className="text-[9px] font-bold text-green-500 uppercase tracking-wider flex items-center gap-0.5">
                      <CheckCircle2 size={11} /> 관리자 답변
                    </span>
                    <div className="bg-green-950/20 p-3 rounded-xl border border-green-900/30 text-slate-200 text-xs whitespace-pre-wrap leading-relaxed">
                      {selectedTicket.answer}
                    </div>
                    {selectedTicket.answered_at && (
                      <p className="text-[9px] text-slate-500 mt-1 text-right">
                        답변 수신: {new Date(selectedTicket.answered_at).toLocaleString("ko-KR")}
                      </p>
                    )}
                  </div>
                ) : (
                  <div className="text-xs text-slate-500 bg-slate-950 p-3 rounded-xl flex items-center gap-2 border border-slate-850">
                    <Clock size={14} className="text-amber-500 shrink-0" />
                    담당 관리자가 질문을 확인하고 있습니다.
                  </div>
                )}
              </div>
            </div>
          ) : (
            /* 탭 브라우징 (새 문의 vs 내 문의 목록) */
            <div className="flex-grow flex flex-col min-h-0 bg-slate-950/20">
              {/* Tab Selector */}
              <div className="flex border-b border-slate-800 shrink-0">
                <button
                  onClick={() => setActiveTab("write")}
                  className={`flex-1 py-3 text-xs font-bold transition-all border-b-2`}
                  style={{
                    color: activeTab === "write" ? (themeConfig.primaryColor || "#2563eb") : "#94a3b8",
                    borderColor: activeTab === "write" ? (themeConfig.primaryColor || "#2563eb") : "transparent",
                    backgroundColor: activeTab === "write" ? "rgba(15,23,42,0.4)" : "transparent"
                  }}
                >
                  새 문의 작성
                </button>
                <button
                  onClick={() => setActiveTab("list")}
                  className={`flex-1 py-3 text-xs font-bold transition-all border-b-2`}
                  style={{
                    color: activeTab === "list" ? (themeConfig.primaryColor || "#2563eb") : "#94a3b8",
                    borderColor: activeTab === "list" ? (themeConfig.primaryColor || "#2563eb") : "transparent",
                    backgroundColor: activeTab === "list" ? "rgba(15,23,42,0.4)" : "transparent"
                  }}
                >
                  나의 문의 내역
                </button>
              </div>

              {/* Tab Body */}
              <div className="flex-1 overflow-y-auto p-4">
                {activeTab === "write" ? (
                  /* 새 문의 폼 */
                  <form onSubmit={handleSubmit} className="space-y-4">
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">문의 제목</label>
                      <input
                        type="text"
                        value={subject}
                        onChange={(e) => setSubject(e.target.value)}
                        placeholder="요약 제목을 입력해 주세요"
                        className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-white placeholder-slate-600 focus:outline-none focus:border-blue-600 text-xs"
                        required
                      />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">문의 내용</label>
                      <textarea
                        value={content}
                        onChange={(e) => setContent(e.target.value)}
                        placeholder="불편한 상황이나 문의사항을 구체적으로 설명해주세요."
                        rows={7}
                        className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2.5 text-white placeholder-slate-600 focus:outline-none focus:border-blue-600 text-xs resize-none leading-relaxed"
                        required
                      />
                    </div>
                    <button
                      type="submit"
                      disabled={submitting}
                      className="w-full text-white py-2.5 rounded-xl text-xs font-bold transition flex items-center justify-center gap-1 shadow-lg shadow-black/10 disabled:opacity-50"
                      style={{ 
                        backgroundColor: themeConfig.primaryColor || "#2563eb",
                        borderRadius: themeConfig.borderRadius === "none" ? "0px" : themeConfig.borderRadius === "sm" ? "4px" : themeConfig.borderRadius === "md" ? "8px" : themeConfig.borderRadius === "lg" ? "16px" : "9999px"
                      }}
                    >
                      {submitting ? (
                        <>
                          <Loader2 className="animate-spin" size={14} /> 접수 중...
                        </>
                      ) : (
                        <>
                          <Send size={13} /> 문의 접수하기
                        </>
                      )}
                    </button>
                  </form>
                ) : (
                  /* 나의 문의 내역 리스트 */
                  <div className="space-y-2.5">
                    {loading ? (
                      <div className="py-20 flex flex-col items-center justify-center text-slate-500">
                        <Loader2 className="animate-spin text-blue-500 mb-2" size={24} />
                        <span className="text-xs">이전 접수 내역을 확인 중...</span>
                      </div>
                    ) : tickets.length === 0 ? (
                      <div className="py-20 text-center text-slate-500">
                        <MessageSquare className="mx-auto text-slate-700 mb-2" size={28} />
                        <p className="text-xs">아직 접수된 문의가 없습니다.</p>
                      </div>
                    ) : (
                      tickets.map((t) => (
                        <div
                          key={t.id}
                          onClick={() => setSelectedTicket(t)}
                          className="p-3 bg-slate-900 hover:bg-slate-850 border border-slate-800 hover:border-slate-755 rounded-xl cursor-pointer transition-all duration-200"
                        >
                          <div className="flex justify-between items-center">
                            <span className={`inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full text-[9px] font-bold border ${
                              t.status === "ANSWERED"
                                ? "bg-green-500/10 text-green-400 border-green-500/20"
                                : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                            }`}>
                              {t.status === "ANSWERED" ? "완료" : "대기"}
                            </span>
                            <span className="text-[9px] text-slate-500 font-mono">
                              {new Date(t.created_at).toLocaleDateString()}
                            </span>
                          </div>
                          <h6 className="text-xs font-bold text-white mt-1.5 truncate leading-tight">
                            {t.subject}
                          </h6>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
