"use client";
import { authFetch, API_URL } from "@/lib/api";

import { useEffect, useState } from "react";
import { User as UserIcon, Shield, ShieldOff, AlertCircle, RefreshCw, Coins, Ticket } from "lucide-react";

interface UserData {
  id: number;
  email: string;
  name: string;
  phone: string | null;
  is_active: boolean;
  role: string | null;
  grade: number;
  reward_points: number;
  created_at: string;
}

const GRADE_LABELS: Record<number, { label: string; bgClass: string; textClass: string }> = {
  0: { label: "관리자 (ADMIN)", bgClass: "bg-rose-500/10", textClass: "text-rose-400 border-rose-500/20" },
  1: { label: "VVIP (적립 5%)", bgClass: "bg-pink-500/10", textClass: "text-pink-400 border-pink-500/20" },
  2: { label: "VIP (적립 3%)", bgClass: "bg-purple-500/10", textClass: "text-purple-400 border-purple-500/20" },
  3: { label: "우수회원 (적립 2%)", bgClass: "bg-blue-500/10", textClass: "text-blue-400 border-blue-500/20" },
  4: { label: "일반회원 (적립 1%)", bgClass: "bg-slate-500/10", textClass: "text-slate-300 border-slate-500/20" },
  5: { label: "미가입회원 (제한)", bgClass: "bg-amber-500/10", textClass: "text-amber-400 border-amber-500/20" },
};

export default function UsersTab() {
  const apiUrl = API_URL;
  const [users, setUsers] = useState<UserData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchUsers = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await authFetch(`${apiUrl}/api/admin/users`);
      if (!res.ok) throw new Error("회원 목록을 불러오는 데 실패했습니다.");
      const data = await res.json();
      setUsers(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleGradeChange = async (userId: number, newGrade: number) => {
    const label = GRADE_LABELS[newGrade]?.label || `${newGrade}등급`;
    if (!confirm(`회원의 등급을 ${label}(으)로 변경하시겠습니까?`)) return;

    try {
      const res = await authFetch(`${apiUrl}/api/admin/users/${userId}/grade`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ grade: newGrade }),
      });
      if (!res.ok) throw new Error("등급 변경에 실패했습니다.");
      await fetchUsers();
    } catch (err: any) {
      alert(err.message);
    }
  };

  // [고도화] 관리자 전용 보유 적립금 강제 수정 기능
  const handleRewardPointsChange = async (userId: number, currentPoints: number) => {
    const input = prompt("변경할 회원의 적립금을 입력하세요 (원 단위):", currentPoints.toString());
    if (input === null) return;
    
    const newPoints = parseInt(input);
    if (isNaN(newPoints) || newPoints < 0) {
      alert("올바른 적립금 숫자를 입력해 주세요. (0 이상의 정수)");
      return;
    }

    try {
      const res = await authFetch(`${apiUrl}/api/admin/users/${userId}/reward-points`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reward_points: newPoints }),
      });
      if (!res.ok) throw new Error("적립금 수정에 실패했습니다.");
      await fetchUsers();
    } catch (err: any) {
      alert(err.message);
    }
  };

  // [고도화] 관리자 전용 수동 할인쿠폰 발급 기능
  const handleIssueCoupon = async (userId: number, userName: string) => {
    const amountInput = prompt(`[${userName}] 회원에게 발급할 쿠폰의 할인 금액을 입력하세요 (원):`, "10000");
    if (amountInput === null) return;
    
    const discountAmount = parseInt(amountInput);
    if (isNaN(discountAmount) || discountAmount <= 0) {
      alert("할인 금액은 1원 이상이어야 합니다.");
      return;
    }

    const nameInput = prompt("할인쿠폰의 이름을 입력하세요:", `본사 특별 ${discountAmount.toLocaleString()}원 할인쿠폰`);
    if (nameInput === null) return;
    
    const couponName = nameInput.trim() || `본사 특별 ${discountAmount.toLocaleString()}원 할인쿠폰`;

    try {
      const res = await authFetch(`${apiUrl}/api/admin/users/${userId}/coupons`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: couponName, discount_amount: discountAmount }),
      });
      if (!res.ok) throw new Error("쿠폰 수동 발급에 실패했습니다.");
      
      alert(`쿠폰 [${couponName}]이(가) 정상적으로 발급 완료되었습니다.`);
      await fetchUsers();
    } catch (err: any) {
      alert(err.message);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold text-white mb-2 tracking-tight">회원 등급 및 혜택(적립금/쿠폰) 관리</h2>
          <p className="text-slate-400">회원 등급 조정 및 수동 적립금 조율, 특별 금액권 할인쿠폰 발급 등의 고도화 혜택을 제어합니다.</p>
        </div>
        <button 
          onClick={fetchUsers} 
          className="bg-slate-800 hover:bg-slate-700 text-white px-4 py-2 rounded-lg flex items-center transition-colors"
        >
          <RefreshCw size={16} className={`mr-2 ${loading ? 'animate-spin' : ''}`} /> 새로고침
        </button>
      </div>

      {error && (
        <div className="bg-red-900/40 border border-red-800 text-red-200 p-4 rounded-lg flex items-center">
          <AlertCircle className="mr-3 text-red-400" size={20} />
          {error}
        </div>
      )}

      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-2xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-800 border-b border-slate-700">
                <th className="p-4 text-xs font-semibold text-slate-300 uppercase tracking-wider">ID</th>
                <th className="p-4 text-xs font-semibold text-slate-300 uppercase tracking-wider">회원 정보 (이름/이메일)</th>
                <th className="p-4 text-xs font-semibold text-slate-300 uppercase tracking-wider">가입 상태</th>
                <th className="p-4 text-xs font-semibold text-slate-300 uppercase tracking-wider">보유 적립금</th>
                <th className="p-4 text-xs font-semibold text-slate-300 uppercase tracking-wider">회원 등급 (Grade)</th>
                <th className="p-4 text-xs font-semibold text-slate-300 uppercase tracking-wider">시스템 권한</th>
                <th className="p-4 text-xs font-semibold text-slate-300 uppercase tracking-wider">가입일</th>
                <th className="p-4 text-xs font-semibold text-slate-300 uppercase tracking-wider text-right">혜택 관리</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {loading ? (
                <tr>
                  <td colSpan={8} className="p-8 text-center text-slate-500">
                    로딩 중...
                  </td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan={8} className="p-8 text-center text-slate-500">
                    가입된 회원 정보가 없습니다.
                  </td>
                </tr>
              ) : (
                users.map((user) => {
                  const gradeInfo = GRADE_LABELS[user.grade] || { label: `등급 ${user.grade}`, bgClass: "bg-slate-500/10", textClass: "text-slate-300 border-slate-500/20" };
                  
                  return (
                    <tr key={user.id} className="hover:bg-slate-800/50 transition-colors">
                      <td className="p-4 text-slate-400">#{user.id}</td>
                      <td className="p-4 font-medium text-white">
                        <div className="flex items-center space-x-2">
                          <UserIcon size={16} className="text-slate-500 flex-shrink-0" />
                          <div>
                            <div className="font-semibold text-sm">{user.name || "이름 미입력"}</div>
                            <div className="text-xs text-slate-400">{user.email}</div>
                          </div>
                        </div>
                      </td>
                      <td className="p-4">
                        <span className={`px-2 py-1 rounded text-xs font-medium ${user.is_active ? 'bg-green-500/10 text-green-400 border border-green-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20'}`}>
                          {user.is_active ? "활성" : "정지"}
                        </span>
                      </td>
                      <td className="p-4 font-semibold text-amber-400">
                        <div className="flex items-center space-x-2">
                          <Coins size={14} className="text-amber-500" />
                          <span>{(user.reward_points || 0).toLocaleString()}원</span>
                          <button
                            onClick={() => handleRewardPointsChange(user.id, user.reward_points || 0)}
                            className="bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white px-2 py-0.5 text-[10px] font-bold rounded border border-slate-700 transition-colors"
                          >
                            수정
                          </button>
                        </div>
                      </td>
                      <td className="p-4">
                        <div className="flex items-center space-x-2">
                          <span className={`px-2 py-1 rounded text-xs font-bold border ${gradeInfo.bgClass} ${gradeInfo.textClass}`}>
                            {gradeInfo.label}
                          </span>
                          <select
                            value={user.grade}
                            onChange={(e) => handleGradeChange(user.id, parseInt(e.target.value))}
                            className="bg-slate-800 hover:bg-slate-700 text-white text-xs border border-slate-700 rounded px-2 py-1 focus:ring-2 focus:ring-purple-500 focus:outline-none cursor-pointer transition-all"
                          >
                            <option value={0}>0등급 - 관리자</option>
                            <option value={1}>1등급 - VVIP (5%)</option>
                            <option value={2}>2등급 - VIP (3%)</option>
                            <option value={3}>3등급 - 우수회원 (2%)</option>
                            <option value={4}>4등급 - 일반회원 (1%)</option>
                            <option value={5}>5등급 - 미가입회원 (제한)</option>
                          </select>
                        </div>
                      </td>
                      <td className="p-4">
                        <span className={`px-2 py-1 rounded text-xs font-bold inline-flex items-center ${user.role === 'ADMIN' ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' : 'bg-blue-500/10 text-blue-400 border border-blue-500/20'}`}>
                          {user.role === 'ADMIN' ? <Shield size={12} className="mr-1" /> : <ShieldOff size={12} className="mr-1" />}
                          {user.role || "USER"}
                        </span>
                      </td>
                      <td className="p-4 text-slate-400 text-sm">
                        {user.created_at ? new Date(user.created_at).toLocaleDateString() : "-"}
                      </td>
                      <td className="p-4 text-right">
                        <button
                          onClick={() => handleIssueCoupon(user.id, user.name || user.email)}
                          className="bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold px-3 py-1.5 rounded-lg shadow-md transition-colors inline-flex items-center space-x-1"
                        >
                          <Ticket size={12} />
                          <span>쿠폰 발급</span>
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
