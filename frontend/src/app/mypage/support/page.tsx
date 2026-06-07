"use client";

import { useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import {
  MessageSquare,
  Plus,
  Loader2,
  ChevronDown,
  ChevronUp,
  Clock,
  CheckCircle2,
  Send,
  Inbox,
} from "lucide-react";

interface Ticket {
  id: number;
  subject: string;
  content: string;
  status: string;
  answer: string | null;
  answered_at: string | null;
  created_at: string;
}

export default function SupportPage() {
  const apiUrl = API_URL;
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  // Form
  const [subject, setSubject] = useState("");
  const [content, setContent] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const fetchTickets = async () => {
    setLoading(true);
    const token = localStorage.getItem("token");
    if (!token) return;
    try {
      const res = await fetch(`${apiUrl}/api/support/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setTickets(await res.json());
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTickets();
  }, []);

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
        setIsFormOpen(false);
        fetchTickets();
      } else {
        alert("문의 접수에 실패했습니다.");
      }
    } catch (err) {
      console.error(err);
    } finally {
      setSubmitting(false);
    }
  };

  const statusBadge = (status: string) => {
    const map: Record<string, { label: string; cls: string; icon: React.ReactNode }> = {
      PENDING: {
        label: "답변 대기",
        cls: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
        icon: <Clock size={12} />,
      },
      ANSWERED: {
        label: "답변 완료",
        cls: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
        icon: <CheckCircle2 size={12} />,
      },
      CLOSED: {
        label: "종료",
        cls: "bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400",
        icon: <CheckCircle2 size={12} />,
      },
    };
    const s = map[status] || map.PENDING;
    return (
      <span
        className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold ${s.cls}`}
      >
        {s.icon} {s.label}
      </span>
    );
  };

  if (loading)
    return (
      <div className="py-20 flex justify-center">
        <Loader2 className="animate-spin text-slate-400" size={32} />
      </div>
    );

  return (
    <div className="bg-white dark:bg-slate-800 rounded-3xl shadow-sm border border-slate-200/60 dark:border-slate-700 p-8 sm:p-10">
      {/* Header */}
      <div className="flex items-center justify-between mb-8 pb-6 border-b border-slate-100 dark:border-slate-700">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-3">
            <MessageSquare className="text-blue-600" size={28} /> 1:1 문의
          </h1>
          <p className="text-sm text-slate-500 mt-2">
            궁금한 점이나 개선 요청사항을 남겨주세요.
          </p>
        </div>
        <button
          onClick={() => setIsFormOpen(!isFormOpen)}
          className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl flex items-center gap-2 transition"
        >
          <Plus size={18} /> 새 문의
        </button>
      </div>

      {/* New Ticket Form */}
      {isFormOpen && (
        <form
          onSubmit={handleSubmit}
          className="mb-8 p-6 bg-blue-50/50 dark:bg-slate-900/50 rounded-2xl border border-blue-100 dark:border-slate-700 space-y-4"
        >
          <div>
            <label className="block text-xs font-bold text-slate-500 mb-1.5">
              제목
            </label>
            <input
              required
              type="text"
              placeholder="간단히 요약해 주세요"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm font-medium focus:ring-2 focus:ring-blue-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-xs font-bold text-slate-500 mb-1.5">
              문의 내용
            </label>
            <textarea
              required
              rows={5}
              placeholder="상세하게 작성해 주시면 빠른 답변에 도움이 됩니다."
              value={content}
              onChange={(e) => setContent(e.target.value)}
              className="w-full px-4 py-3 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm font-medium focus:ring-2 focus:ring-blue-500 focus:outline-none resize-none"
            />
          </div>
          <div className="flex gap-3 justify-end">
            <button
              type="button"
              onClick={() => setIsFormOpen(false)}
              className="px-5 py-2.5 text-slate-500 font-bold bg-slate-100 hover:bg-slate-200 rounded-xl transition"
            >
              취소
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl flex items-center gap-2 transition disabled:opacity-60"
            >
              {submitting ? (
                <Loader2 className="animate-spin" size={16} />
              ) : (
                <Send size={16} />
              )}
              접수하기
            </button>
          </div>
        </form>
      )}

      {/* Ticket List */}
      {tickets.length === 0 ? (
        <div className="py-20 text-center bg-slate-50 dark:bg-slate-900/40 rounded-2xl border border-dashed border-slate-300 dark:border-slate-700">
          <div className="w-16 h-16 bg-white dark:bg-slate-800 rounded-full flex items-center justify-center mx-auto mb-4 text-slate-400">
            <Inbox size={32} />
          </div>
          <h3 className="text-lg font-bold text-slate-700 dark:text-slate-300">
            아직 접수된 문의가 없습니다
          </h3>
          <p className="text-slate-500 mt-2 text-sm">
            상단의 &ldquo;새 문의&rdquo; 버튼으로 질문을 남겨보세요.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {tickets.map((ticket) => {
            const isExpanded = expandedId === ticket.id;
            return (
              <div
                key={ticket.id}
                className="border border-slate-200 dark:border-slate-700 rounded-2xl overflow-hidden bg-white dark:bg-slate-800 transition-shadow hover:shadow-sm"
              >
                {/* Row Header */}
                <button
                  onClick={() =>
                    setExpandedId(isExpanded ? null : ticket.id)
                  }
                  className="w-full flex items-center justify-between px-6 py-4 text-left"
                >
                  <div className="flex items-center gap-4 min-w-0">
                    {statusBadge(ticket.status)}
                    <span className="font-bold text-slate-900 dark:text-white truncate">
                      {ticket.subject}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 flex-shrink-0 ml-4">
                    <span className="text-xs text-slate-400 font-medium hidden sm:inline">
                      {new Date(ticket.created_at).toLocaleDateString("ko-KR")}
                    </span>
                    {isExpanded ? (
                      <ChevronUp size={18} className="text-slate-400" />
                    ) : (
                      <ChevronDown size={18} className="text-slate-400" />
                    )}
                  </div>
                </button>

                {/* Expanded Detail */}
                {isExpanded && (
                  <div className="px-6 pb-6 pt-2 border-t border-slate-100 dark:border-slate-700 space-y-5">
                    {/* My Question */}
                    <div>
                      <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">
                        내 문의
                      </h4>
                      <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed whitespace-pre-wrap bg-slate-50 dark:bg-slate-900/50 p-4 rounded-xl">
                        {ticket.content}
                      </p>
                    </div>

                    {/* Admin Answer */}
                    {ticket.answer ? (
                      <div>
                        <h4 className="text-xs font-bold text-green-600 uppercase tracking-wider mb-2 flex items-center gap-1">
                          <CheckCircle2 size={14} /> 관리자 답변
                        </h4>
                        <div className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed whitespace-pre-wrap bg-green-50 dark:bg-green-900/10 p-4 rounded-xl border border-green-100 dark:border-green-900/30">
                          {ticket.answer}
                        </div>
                        {ticket.answered_at && (
                          <p className="text-xs text-slate-400 mt-2 text-right">
                            답변일:{" "}
                            {new Date(ticket.answered_at).toLocaleString(
                              "ko-KR"
                            )}
                          </p>
                        )}
                      </div>
                    ) : (
                      <div className="text-sm text-slate-400 bg-slate-50 dark:bg-slate-900/50 p-4 rounded-xl flex items-center gap-2">
                        <Clock size={16} className="text-amber-500" />
                        아직 답변이 등록되지 않았습니다. 조금만 기다려 주세요.
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
