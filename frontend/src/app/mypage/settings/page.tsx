"use client";

import { useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { Settings, Camera, Loader2, AlertTriangle, Crown, Ruler, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";

export default function SettingsPage() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const { user, login, logout } = useAuth();
  const router = useRouter();
  const [name, setName] = useState(user?.name || "");
  const [phone, setPhone] = useState((user as any)?.phone || "");
  const [saving, setSaving] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  
  // AI Body Profile (임시 상태)
  const [height, setHeight] = useState("");
  const [weight, setWeight] = useState("");
  const [usualSize, setUsualSize] = useState("M");

  const handleSave = async () => {
    setSaving(true);
    const token = localStorage.getItem("token");
    try {
      const res = await fetch(`${apiUrl}/api/auth/me`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ name, phone }), // 체형 정보는 추후 백엔드 확장 시 전송 가능
      });
      if (res.ok) {
        const data = await res.json();
        login(token!, data);
        alert("기본 프로필이 저장되었습니다.");
      }
    } catch { alert("저장 실패"); }
    finally { setSaving(false); }
  };

  const handleProfileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const token = localStorage.getItem("token");
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await fetch(`${apiUrl}/api/auth/me/profile-image`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });
      if (res.ok) {
        const data = await res.json();
        login(token!, data); // user 객체가 갱신되며 이미지 즉각 리렌더링 됨
      } else {
        alert("업로드 실패 (서버 오류)");
      }
    } catch { alert("업로드 실패 (네트워크 오류)"); }
  };

  const handleDeleteAccount = async () => {
    const token = localStorage.getItem("token");
    try {
      const res = await fetch(`${apiUrl}/api/auth/me`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        logout();
        router.push("/");
      }
    } catch { alert("탈퇴 처리 실패"); }
  };

  return (
    <div className="bg-white dark:bg-slate-800 rounded-3xl shadow-sm border border-slate-200/60 dark:border-slate-700 p-8 sm:p-10">
      <div className="mb-8 pb-6 border-b border-slate-100 dark:border-slate-700 flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-3"><Settings className="text-blue-600" size={28} /> Settings</h1>
          <p className="text-sm text-slate-500 mt-2">프로필 및 계정 설정을 관리하세요.</p>
        </div>
      </div>

      {/* Membership Banner */}
      <div className="mb-10 bg-gradient-to-r from-blue-600 to-indigo-600 rounded-2xl p-6 text-white shadow-md relative overflow-hidden">
         <div className="absolute top-0 right-0 p-8 opacity-10"><Crown size={120} /></div>
         <div className="relative z-10 flex flex-col sm:flex-row items-start sm:items-center justify-between">
            <div>
               <div className="flex items-center gap-2 mb-1">
                 <Crown size={18} className="text-yellow-300" />
                 <span className="text-sm font-bold text-blue-100 uppercase tracking-widest">VIP 멤버십</span>
               </div>
               <h2 className="text-2xl font-bold">{user?.name || "사용자"} 님은 현재 <span className="text-yellow-300">GOLD</span> 등급입니다.</h2>
            </div>
            <div className="mt-4 sm:mt-0 text-right">
               <p className="text-xs text-blue-200">보유 포인트</p>
               <p className="text-3xl font-bold">12,500 <span className="text-lg font-medium">P</span></p>
            </div>
         </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-12">
        {/* Left Column: Profile & Contact */}
        <div>
            {/* Profile Image */}
            <div className="mb-8">
                <h3 className="text-sm font-bold text-slate-500 uppercase tracking-widest mb-4">프로필 사진</h3>
                <div className="flex items-center gap-6">
                <div className="w-20 h-20 rounded-full bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center text-white text-2xl font-bold overflow-hidden ring-4 ring-slate-50 dark:ring-slate-800 shadow-md">
                    {user?.profile_image ? (
                    <img src={user.profile_image.startsWith("http") ? user.profile_image : `${apiUrl}${user.profile_image}`} alt="프로필" className="w-full h-full object-cover" />
                    ) : user?.name?.charAt(0)}
                </div>
                <div>
                   <label className="cursor-pointer px-5 py-2.5 bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-300 font-bold rounded-xl flex items-center gap-2 transition text-sm">
                       <Camera size={16} /> 사진 변경
                       <input type="file" accept="image/*" onChange={handleProfileUpload} className="hidden" />
                   </label>
                   <p className="text-xs text-slate-400 mt-2 ml-1">JPG, PNG 5MB 이하</p>
                </div>
                </div>
            </div>

            {/* Name & Phone */}
            <div className="space-y-5 mb-8">
                <div>
                <label className="block text-xs font-bold text-slate-500 mb-1.5">이름</label>
                <input type="text" value={name} onChange={e => setName(e.target.value)} className="w-full max-w-md px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none" />
                </div>
                <div>
                <label className="block text-xs font-bold text-slate-500 mb-1.5">전화번호</label>
                <input type="text" value={phone} onChange={e => setPhone(e.target.value)} placeholder="010-0000-0000" className="w-full max-w-md px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none" />
                </div>
                <button onClick={handleSave} disabled={saving} className="px-8 py-3 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl transition disabled:opacity-50 flex items-center justify-center gap-2 max-w-md w-full">
                {saving ? <Loader2 className="animate-spin" size={18} /> : null} 기본 정보 저장하기
                </button>
            </div>
        </div>

        {/* Right Column: Body Profile */}
        <div>
           <div className="bg-blue-50 dark:bg-slate-900/50 rounded-3xl p-8 border border-blue-100 dark:border-slate-700 relative">
              <div className="absolute top-4 right-4 bg-white dark:bg-slate-800 p-2 rounded-xl shadow-sm border border-slate-100 dark:border-slate-700">
                 <Sparkles className="text-blue-500" size={20} />
              </div>
              <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-2 flex items-center gap-2"><Ruler size={20} className="text-blue-600" /> AI 체형 프로필</h3>
              <p className="text-sm text-slate-500 mb-6 leading-relaxed">자신의 체형 정보를 입력해 두세요. AI 피팅 스튜디오 이용 시 고객님의 체형을 분석하여 가장 완벽한 핏을 추천해 드립니다.</p>
              
              <div className="grid grid-cols-2 gap-4 mb-4">
                 <div>
                    <label className="block text-xs font-bold text-slate-500 mb-1.5">키 (cm)</label>
                    <input type="number" placeholder="예: 175" value={height} onChange={e=>setHeight(e.target.value)} className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none" />
                 </div>
                 <div>
                    <label className="block text-xs font-bold text-slate-500 mb-1.5">몸무게 (kg)</label>
                    <input type="number" placeholder="예: 65" value={weight} onChange={e=>setWeight(e.target.value)} className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none" />
                 </div>
              </div>
              <div className="mb-6">
                 <label className="block text-xs font-bold text-slate-500 mb-1.5">평소 입는 상하의 사이즈</label>
                 <select value={usualSize} onChange={e=>setUsualSize(e.target.value)} className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none appearance-none">
                    <option value="S">S (Small) / 90</option>
                    <option value="M">M (Medium) / 95</option>
                    <option value="L">L (Large) / 100</option>
                    <option value="XL">XL (X-Large) / 105</option>
                    <option value="XXL">XXL (2X-Large) / 110</option>
                 </select>
              </div>
              <button className="w-full px-6 py-2.5 bg-slate-800 dark:bg-blue-600 hover:bg-slate-900 dark:hover:bg-blue-500 text-white font-bold rounded-xl transition text-sm">
                 체형 정보 업데이트
              </button>
           </div>
        </div>
      </div>

      {/* Delete Account */}
      <div className="pt-8 mt-4 border-t border-slate-100 dark:border-slate-700">
        <h3 className="text-sm font-bold text-red-500 uppercase tracking-widest mb-4 flex items-center gap-2"><AlertTriangle size={16} /> 위험 영역</h3>
        {!showDeleteConfirm ? (
          <button onClick={() => setShowDeleteConfirm(true)} className="px-6 py-2.5 border-2 border-red-200 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 font-bold rounded-xl transition text-sm">회원 탈퇴</button>
        ) : (
          <div className="p-4 bg-red-50 dark:bg-red-900/20 rounded-xl border border-red-200 dark:border-red-800 max-w-md">
            <p className="text-sm text-red-600 font-bold mb-4">정말 탈퇴하시겠습니까? 이 작업은 되돌릴 수 없습니다.</p>
            <div className="flex gap-3">
              <button onClick={() => setShowDeleteConfirm(false)} className="px-5 py-2 bg-slate-100 text-slate-600 font-bold rounded-lg text-sm">취소</button>
              <button onClick={handleDeleteAccount} className="px-5 py-2 bg-red-600 text-white font-bold rounded-lg text-sm hover:bg-red-700 transition">탈퇴 진행</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}