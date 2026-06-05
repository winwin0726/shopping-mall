"use client";

import { useEffect, useState } from "react";
import { Plus, MapPin, Edit, Trash2, Loader2, Home, Search, X } from "lucide-react";
import DaumPostcode from 'react-daum-postcode';

interface Address {
  id: number;
  recipient_name: string;
  phone: string;
  postal_code: string;
  address_line1: string;
  address_line2?: string;
  is_default: boolean;
}

export default function AddressesPage() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const [addresses, setAddresses] = useState<Address[]>([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isPostcodeOpen, setIsPostcodeOpen] = useState(false);
  const [editingAddr, setEditingAddr] = useState<Address | null>(null);
  const [formData, setFormData] = useState({ recipient_name: "", phone: "", postal_code: "", address_line1: "", address_line2: "", is_default: false });

  const fetchAddresses = async () => {
    setLoading(true);
    const token = localStorage.getItem("token");
    if (!token) {
      setLoading(false);
      return;
    }
    try {
      const res = await fetch(`${apiUrl}/api/address/me`, { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) setAddresses(await res.json());
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchAddresses(); }, []);

  const openModal = (addr?: Address) => {
    if (addr) {
      setEditingAddr(addr);
      setFormData({ recipient_name: addr.recipient_name, phone: addr.phone, postal_code: addr.postal_code, address_line1: addr.address_line1, address_line2: addr.address_line2 || "", is_default: addr.is_default });
    } else {
      setEditingAddr(null);
      setFormData({ recipient_name: "", phone: "", postal_code: "", address_line1: "", address_line2: "", is_default: addresses.length === 0 });
    }
    setIsPostcodeOpen(false);
    setIsModalOpen(true);
  };

  const handleCompletePostcode = (data: any) => {
    let fullAddress = data.address;
    let extraAddress = '';

    if (data.addressType === 'R') {
      if (data.bname !== '') {
        extraAddress += data.bname;
      }
      if (data.buildingName !== '') {
        extraAddress += extraAddress !== '' ? `, ${data.buildingName}` : data.buildingName;
      }
      fullAddress += extraAddress !== '' ? ` (${extraAddress})` : '';
    }

    setFormData({
      ...formData,
      postal_code: data.zonecode,
      address_line1: fullAddress,
    });
    setIsPostcodeOpen(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if(!formData.postal_code || !formData.address_line1) {
       alert("주소 검색을 통해 주소를 입력해주세요.");
       return;
    }
    const token = localStorage.getItem("token");
    if (!token) return;
    const url = editingAddr ? `${apiUrl}/api/address/${editingAddr.id}` : `${apiUrl}/api/address/`;
    const res = await fetch(url, { method: editingAddr ? "PUT" : "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify(formData) });
    if (res.ok) { setIsModalOpen(false); fetchAddresses(); }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("이 배송지를 삭제하시겠습니까?")) return;
    const token = localStorage.getItem("token");
    await fetch(`${apiUrl}/api/address/${id}`, { method: "DELETE", headers: { Authorization: `Bearer ${token}` } });
    fetchAddresses();
  };

  const handleSetDefault = async (id: number) => {
    const token = localStorage.getItem("token");
    await fetch(`${apiUrl}/api/address/${id}`, { method: "PUT", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify({ is_default: true }) });
    fetchAddresses();
  };

  if (loading) return <div className="py-20 flex justify-center"><Loader2 className="animate-spin text-slate-400" size={32} /></div>;

  return (
    <div className="bg-white dark:bg-slate-800 rounded-3xl shadow-sm border border-slate-200/60 dark:border-slate-700 p-8 sm:p-10">
      <div className="flex items-center justify-between mb-8 pb-6 border-b border-slate-100 dark:border-slate-700">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-3"><MapPin className="text-blue-600" size={28} /> Address Book</h1>
          <p className="text-sm text-slate-500 mt-2">나의 배송지 목록을 관리하고 주문을 더 빠르게 진행하세요.</p>
        </div>
        <button onClick={() => openModal()} className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl flex items-center gap-2 transition"><Plus size={18} /> 새 배송지</button>
      </div>

      {addresses.length === 0 ? (
        <div className="py-20 text-center bg-slate-50 dark:bg-slate-900/40 rounded-2xl border border-dashed border-slate-300 dark:border-slate-700">
          <MapPin size={32} className="mx-auto mb-4 text-slate-400" />
          <h3 className="text-lg font-bold text-slate-700 dark:text-slate-300">등록된 배송지가 없습니다</h3>
          <p className="text-slate-500 mt-2 text-sm">기본 배송지를 등록해두면 빠른 결제가 가능합니다.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {addresses.map(addr => (
            <div key={addr.id} className={`p-6 rounded-2xl border-2 transition relative ${addr.is_default ? "border-blue-500 bg-blue-50/50 dark:bg-blue-900/10" : "border-slate-200 dark:border-slate-700"}`}>
              {addr.is_default && <div className="absolute -top-3 left-6 inline-flex items-center gap-1.5 px-3 py-1 bg-blue-600 text-white text-xs font-bold rounded-full"><Home size={12} /> 기본 배송지</div>}
              <div className="flex justify-between items-start mt-2">
                <div>
                  <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-2">{addr.recipient_name}</h3>
                  <p className="text-slate-600 dark:text-slate-400 text-sm font-mono mb-1">{addr.phone}</p>
                  <p className="text-slate-600 dark:text-slate-400 text-sm mt-3">[{addr.postal_code}]<br />{addr.address_line1} {addr.address_line2}</p>
                </div>
                <div className="flex items-center gap-2">
                  <button onClick={() => openModal(addr)} className="p-2 text-slate-400 hover:text-blue-600 bg-white dark:bg-slate-700 shadow-sm border border-slate-200 dark:border-slate-600 rounded-lg transition"><Edit size={16} /></button>
                  <button onClick={() => handleDelete(addr.id)} className="p-2 text-slate-400 hover:text-red-600 bg-white dark:bg-slate-700 shadow-sm border border-slate-200 dark:border-slate-600 rounded-lg transition"><Trash2 size={16} /></button>
                </div>
              </div>
              {!addr.is_default && <button onClick={() => handleSetDefault(addr.id)} className="mt-6 text-sm font-bold text-slate-400 hover:text-blue-600 transition underline decoration-dashed underline-offset-4">기본 배송지로 설정</button>}
            </div>
          ))}
        </div>
      )}

      {/* 모달 */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="bg-white dark:bg-slate-800 w-full max-w-md rounded-3xl p-8 shadow-2xl relative">
            <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-6">{editingAddr ? "배송지 수정" : "새 배송지 추가"}</h2>
            
            {/* 팝업 모드 렌더링 */}
            {isPostcodeOpen ? (
              <div className="space-y-4">
                 <div className="flex justify-between items-center mb-2">
                    <h3 className="text-sm font-bold text-slate-700 dark:text-slate-300">주소 검색 (지번/도로명)</h3>
                    <button onClick={() => setIsPostcodeOpen(false)} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"><X size={20} /></button>
                 </div>
                 <div className="border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden">
                   <DaumPostcode onComplete={handleCompletePostcode} autoClose style={{ height: '400px', width: '100%' }} />
                 </div>
              </div>
            ) : (
                <form onSubmit={handleSubmit} className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                    <div><label className="block text-xs font-bold text-slate-500 mb-1">수령인</label><input required type="text" value={formData.recipient_name} onChange={e => setFormData({ ...formData, recipient_name: e.target.value })} className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none" /></div>
                    <div><label className="block text-xs font-bold text-slate-500 mb-1">연락처</label><input required type="text" placeholder="010-0000-0000" value={formData.phone} onChange={e => setFormData({ ...formData, phone: e.target.value })} className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none" /></div>
                </div>
                
                {/* 우편번호 & 주소 검색 영역 */}
                <div>
                    <label className="block text-xs font-bold text-slate-500 mb-1">주소</label>
                    <div className="flex gap-2 mb-2">
                        <input readOnly type="text" placeholder="우편번호" value={formData.postal_code} className="w-1/3 px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 text-sm text-slate-600 dark:text-slate-400 cursor-not-allowed" />
                        <button type="button" onClick={() => setIsPostcodeOpen(true)} className="flex-1 px-4 py-2.5 bg-slate-800 hover:bg-slate-900 dark:bg-blue-600 dark:hover:bg-blue-500 text-white font-bold rounded-xl text-sm flex items-center justify-center gap-2 transition">
                            <Search size={16} /> 신주소 / 구주소 검색
                        </button>
                    </div>
                    <input readOnly type="text" value={formData.address_line1} placeholder="기본 주소가 검색됩니다" className="w-full px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 text-sm text-slate-600 dark:text-slate-400 cursor-not-allowed mb-2" />
                    
                    <input required type="text" value={formData.address_line2} placeholder="상세 주소를 입력해주세요" onChange={e => setFormData({ ...formData, address_line2: e.target.value })} className="w-full px-4 py-2.5 rounded-xl border border-blue-200 dark:border-blue-700/50 bg-white dark:bg-slate-900 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none" />
                </div>
                <label className="flex items-center gap-2 mt-4 cursor-pointer"><input type="checkbox" checked={formData.is_default} onChange={e => setFormData({ ...formData, is_default: e.target.checked })} className="w-4 h-4 text-blue-600 rounded" /><span className="text-sm font-bold text-slate-700 dark:text-slate-300">기본 배송지로 설정</span></label>
                <div className="flex gap-3 pt-6"><button type="button" onClick={() => setIsModalOpen(false)} className="flex-1 py-3 text-slate-500 font-bold bg-slate-100 dark:bg-slate-700/50 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-xl transition">취소</button><button type="submit" className="flex-1 py-3 text-white font-bold bg-blue-600 hover:bg-blue-700 rounded-xl transition">저장</button></div>
                </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}