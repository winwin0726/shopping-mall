"use client";
import { authFetch } from "@/lib/api";

import { useEffect, useState } from "react";
import { 
  MessageSquare, Clock, CheckCircle2, Trash2, Edit, AlertCircle, RefreshCw, Send, X, User
} from "lucide-react";

interface TicketData {
  id: number;
  user_id: number;
  user_email: string;
  user_name: string;
  subject: string;
  content: string;
  status: string; // PENDING | ANSWERED
  answer: string | null;
  answered_at: string | null;
  created_at: string;
}

export default function SupportTab() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";
  const [tickets, setTickets] = useState<TicketData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"ALL" | "PENDING" | "ANSWERED">("ALL");

  // Selected Ticket for details & answering
  const [selectedTicket, setSelectedTicket] = useState<TicketData | null>(null);
  const [answerContent, setAnswerContent] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const fetchTickets = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await authFetch(`${apiUrl}/api/admin/support/tickets`);
      if (!res.ok) throw new Error("1:1 문의 목록을 불러오는 데 실패했습니다.");
      const data = await res.json();
      setTickets(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectTicket = (ticket: TicketData) => {
    setSelectedTicket(ticket);
    setAnswerContent(ticket.answer || "");
  };

  const handleAnswerSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTicket || !answerContent.trim()) return;

    setSubmitting(true);
    try {
      const res = await authFetch(`${apiUrl}/api/admin/support/tickets/${selectedTicket.id}/answer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answer: answerContent })
      });

      if (!res.ok) throw new Error("답변 등록에 실패했습니다.");
      
      alert("답변이 성공적으로 등록되었습니다.");
      setSelectedTicket(null);
      setAnswerContent("");
      await fetchTickets();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteTicket = async (id: number) => {
    if (!confirm("이 1:1 문의 내역을 영구 삭제하시겠습니까?\n유저 화면에서도 내역이 삭제됩니다.")) return;

    try {
      const res = await authFetch(`${apiUrl}/api/admin/support/tickets/${id}`, {
        method: "DELETE"
      });
      if (!res.ok) throw new Error("문의글 삭제에 실패했습니다.");
      
      alert("문의글이 삭제되었습니다.");
      if (selectedTicket?.id === id) {
        setSelectedTicket(null);
      }
      await fetchTickets();
    } catch (err: any) {
      alert(err.message);
    }
  };

  useEffect(() => {
    fetchTickets();
  }, []);

  const filteredTickets = tickets.filter(t => {
    if (filter === "ALL") return true;
    return t.status === filter;
  });

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Top Bar */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold text-white mb-2 tracking-tight">1:1 문의 관리 (Customer Q&A)</h2>
          <p className="text-slate-400">쇼핑몰 입점 고객들이 등록한 1:1 질문 내역을 확인하고 답변을 작성합니다.</p>
        </div>
        <div className="flex gap-2">
          {/* Status Filters */}
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-1 flex">
            {(["ALL", "PENDING", "ANSWERED"] as const).map((opt) => (
              <button
                key={opt}
                onClick={() => setFilter(opt)}
                className={`px-3.5 py-1.5 rounded-md text-xs font-bold transition-all ${
                  filter === opt 
                    ? "bg-blue-600 text-white shadow-md shadow-blue-500/10" 
                    : "text-slate-400 hover:text-white"
                }`}
              >
                {opt === "ALL" && "전체"}
                {opt === "PENDING" && "답변 대기"}
                {opt === "ANSWERED" && "답변 완료"}
              </button>
            ))}
          </div>

          <button 
            onClick={fetchTickets} 
            className="bg-slate-800 hover:bg-slate-700 text-white px-4 py-2 rounded-lg flex items-center transition-colors text-sm font-semibold"
          >
            <RefreshCw size={16} className={`mr-2 ${loading ? 'animate-spin' : ''}`} /> 새로고침
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-900/40 border border-red-800 text-red-200 p-4 rounded-lg flex items-center">
          <AlertCircle className="mr-3 text-red-400" size={20} />
          {error}
        </div>
      )}

      {/* Main Grid: Ticket List vs Ticket Detail */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* Left Column: List (7/12) */}
        <div className="lg:col-span-7 space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-2xl">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-slate-800 border-b border-slate-700">
                    <th className="p-4 text-xs font-semibold text-slate-300 uppercase tracking-wider">상태</th>
                    <th className="p-4 text-xs font-semibold text-slate-300 uppercase tracking-wider">문의 제목</th>
                    <th className="p-4 text-xs font-semibold text-slate-300 uppercase tracking-wider">작성자</th>
                    <th className="p-4 text-xs font-semibold text-slate-300 uppercase tracking-wider">접수일</th>
                    <th className="p-4 text-xs font-semibold text-slate-300 uppercase tracking-wider text-right">삭제</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {loading ? (
                    <tr>
                      <td colSpan={5} className="p-8 text-center text-slate-500">
                        로딩 중...
                      </td>
                    </tr>
                  ) : filteredTickets.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="p-8 text-center text-slate-500">
                        해당 조건의 1:1 문의글이 없습니다.
                      </td>
                    </tr>
                  ) : (
                    filteredTickets.map((ticket) => (
                      <tr 
                        key={ticket.id} 
                        onClick={() => handleSelectTicket(ticket)}
                        className={`cursor-pointer transition-colors ${
                          selectedTicket?.id === ticket.id 
                            ? "bg-blue-600/10 hover:bg-blue-600/15" 
                            : "hover:bg-slate-800/50"
                        }`}
                      >
                        <td className="p-4">
                          <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold border ${
                            ticket.status === "ANSWERED"
                              ? "bg-green-500/10 text-green-400 border-green-500/20"
                              : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                          }`}>
                            {ticket.status === "ANSWERED" ? <CheckCircle2 size={10} /> : <Clock size={10} />}
                            {ticket.status === "ANSWERED" ? "완료" : "대기"}
                          </span>
                        </td>
                        <td className="p-4 font-semibold text-white truncate max-w-[200px]" title={ticket.subject}>
                          {ticket.subject}
                        </td>
                        <td className="p-4 text-slate-300 text-sm">
                          <div className="font-semibold">{ticket.user_name}</div>
                          <div className="text-[10px] text-slate-500 font-mono">{ticket.user_email}</div>
                        </td>
                        <td className="p-4 text-slate-400 text-xs font-mono">
                          {new Date(ticket.created_at).toLocaleDateString()}
                        </td>
                        <td className="p-4 text-right" onClick={(e) => e.stopPropagation()}>
                          <button
                            onClick={() => handleDeleteTicket(ticket.id)}
                            className="p-1.5 text-slate-400 hover:text-red-400 hover:bg-red-950/20 rounded transition"
                            title="문의글 강제삭제"
                          >
                            <Trash2 size={15} />
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Right Column: Detail & Reply Form (5/12) */}
        <div className="lg:col-span-5">
          {selectedTicket ? (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-5 shadow-2xl animate-in fade-in slide-in-from-right-4 duration-300">
              
              {/* Detail Header */}
              <div className="flex justify-between items-start border-b border-slate-800 pb-3">
                <div>
                  <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold border ${
                    selectedTicket.status === "ANSWERED"
                      ? "bg-green-500/10 text-green-400 border-green-500/20"
                      : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                  }`}>
                    {selectedTicket.status === "ANSWERED" ? "답변 완료" : "답변 대기 중"}
                  </span>
                  <h3 className="text-base font-bold text-white mt-2 leading-snug">{selectedTicket.subject}</h3>
                </div>
                <button 
                  onClick={() => setSelectedTicket(null)} 
                  className="text-slate-500 hover:text-white bg-slate-800/80 p-1 rounded-lg transition"
                >
                  <X size={16} />
                </button>
              </div>

              {/* User info */}
              <div className="flex items-center gap-2.5 bg-slate-950 p-3 rounded-lg border border-slate-850">
                <div className="w-8 h-8 rounded-full bg-blue-600/20 text-blue-400 flex items-center justify-center font-bold">
                  <User size={16} />
                </div>
                <div className="text-xs">
                  <div className="font-bold text-slate-200">{selectedTicket.user_name}</div>
                  <div className="text-slate-400 font-mono mt-0.5">{selectedTicket.user_email}</div>
                </div>
              </div>

              {/* Question Content */}
              <div className="space-y-1.5">
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">문의 상세 내용</span>
                <div className="bg-slate-950/80 border border-slate-850 p-4 rounded-xl text-slate-350 text-sm whitespace-pre-wrap leading-relaxed">
                  {selectedTicket.content}
                </div>
                <div className="text-[10px] text-slate-500 text-right pt-1 font-mono">
                  등록 일시: {new Date(selectedTicket.created_at).toLocaleString()}
                </div>
              </div>

              {/* Reply Form */}
              <form onSubmit={handleAnswerSubmit} className="space-y-3.5 border-t border-slate-800 pt-4">
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
                  {selectedTicket.answer ? "작성된 답변 내용 (수정 가능)" : "관리자 답변 달기"}
                </span>
                
                <textarea
                  value={answerContent}
                  onChange={(e) => setAnswerContent(e.target.value)}
                  placeholder="고객의 불편 사항에 대한 답변과 조치 예정 내용을 남겨주세요."
                  rows={6}
                  className="w-full bg-slate-950 border border-slate-850 rounded-xl px-4 py-3 text-white placeholder-slate-600 focus:outline-none focus:border-blue-600 text-sm leading-relaxed resize-none"
                  required
                />

                <div className="flex justify-end pt-1">
                  <button
                    type="submit"
                    disabled={submitting}
                    className="bg-blue-600 hover:bg-blue-500 text-white font-semibold text-sm px-5 py-2.5 rounded-lg transition shadow-lg shadow-blue-500/10 flex items-center gap-1.5 disabled:opacity-50"
                  >
                    <Send size={15} />
                    {selectedTicket.answer ? "답변 수정하기" : "답변 전송 및 승인"}
                  </button>
                </div>
              </form>

            </div>
          ) : (
            <div className="bg-slate-900/40 border border-dashed border-slate-800 rounded-xl p-16 text-center text-slate-600 flex flex-col items-center justify-center h-full min-h-[300px]">
              <MessageSquare size={36} className="mb-3 text-slate-700" />
              <h4 className="text-sm font-semibold text-slate-400">조회할 문의글을 선택해주세요</h4>
              <p className="text-xs text-slate-500 mt-1 max-w-[220px] leading-normal">목록에서 접수된 고객의 문의글을 선택하면 상세 내용 조회 및 답변을 작성할 수 있습니다.</p>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
