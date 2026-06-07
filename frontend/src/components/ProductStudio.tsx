"use client";
import { authFetch, API_URL } from "@/lib/api";

import React, { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { X, UploadCloud, ImageIcon, Loader2, Tag, Box, DollarSign, Image as FileImage } from "lucide-react";
import { useDropzone } from "react-dropzone";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import ImageExtension from "@tiptap/extension-image";

interface ProductStudioProps {
  product?: any;
  categories: any[];
  onClose: () => void;
  onSaved: () => void;
}

export default function ProductStudio({ product, categories, onClose, onSaved }: ProductStudioProps) {
  const apiUrl = API_URL;
  const isEdit = !!product;

  const [form, setForm] = useState({
    kr_name: product?.kr_name || "",
    kr_description: product?.kr_description || "",
    base_price: product?.base_price || 0,
    sale_price: product?.sale_price || 0,
    stock_quantity: product?.stock_quantity || 0,
    sku: product?.sku || "",
    category_id: product?.category_id || (categories[0]?.id || 1),
    status: product?.status || "APPROVED",
    keywords: product?.keywords ? product.keywords.join(", ") : "",
    ai_fitting_image_url: product?.ai_fitting_image_url || null,
    images: product?.images || [], // 갤러리 이미지
    cn_name: product?.cn_name || "",
    description_html: product?.description_html || "",
  });

  const [saving, setSaving] = useState(false);
  const [uploadingImage, setUploadingImage] = useState(false);

  // === Tiptap Editor Setup ===
  const editor = useEditor({
    extensions: [StarterKit, ImageExtension],
    content: form.description_html || "<p>상품 상세 설명을 입력하세요...</p>",
    immediatelyRender: false,
    onUpdate: ({ editor }) => {
      setForm(prev => ({ ...prev, description_html: editor.getHTML() }));
    },
    editorProps: {
      attributes: {
        class: "prose prose-sm dark:prose-invert max-w-none focus:outline-none min-h-[300px] p-4",
      },
    },
  });

  // Tiptap 에디터 이미지 삽입
  const insertImageToEditor = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !editor) return;
    try {
      const url = await uploadFile(file);
      editor.chain().focus().setImage({ src: url }).run();
    } catch (err) {
      alert("이미지 업로드 실패");
    }
  };

  const uploadFile = async (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    const res = await authFetch(`${apiUrl}/api/admin/upload`, {
      method: "POST",
      body: formData,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);
    return data.url;
  };

  // === Dropzone Setup for Main/Gallery Media ===
  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    setUploadingImage(true);
    try {
      const urls = await Promise.all(acceptedFiles.map(file => uploadFile(file)));
      setForm(prev => {
        const newImages = [...prev.images, ...urls];
        return {
          ...prev,
          images: newImages,
          ai_fitting_image_url: prev.ai_fitting_image_url || urls[0] // 첫 번째를 대표 이미지로
        };
      });
    } catch (err) {
      alert("일부 파일 업로드에 실패했습니다.");
    } finally {
      setUploadingImage(false);
    }
  }, []);
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "image/*": [] },
    multiple: true
  });

  const removeGalleryImage = (index: number) => {
    setForm(prev => {
      const newImages = [...prev.images];
      newImages.splice(index, 1);
      return { ...prev, images: newImages };
    });
  };

  const handleChange = (field: string, value: any) => {
    setForm(prev => ({ ...prev, [field]: value }));
  };

  // 할인율 자동 계산
  const discountRate = form.base_price > 0 && form.sale_price > 0 && form.sale_price < form.base_price
    ? Math.round(((form.base_price - form.sale_price) / form.base_price) * 100) : 0;

  const handleSubmit = async () => {
    if (!form.kr_name.trim()) return alert("상품명을 입력해주세요.");
    if (form.base_price <= 0) return alert("가격은 0보다 커야 합니다.");

    setSaving(true);
    try {
      const url = isEdit
        ? `${apiUrl}/api/admin/product/${product.id}`
        : `${apiUrl}/api/admin/product`;
      const method = isEdit ? "PUT" : "POST";
      
      const payload = {
        ...form,
        discount_rate: discountRate,
        keywords: form.keywords.split(",").map((k: string) => k.trim()).filter(Boolean)
      };

      const res = await authFetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error("저장 실패");
      onSaved();
    } catch (err) {
      console.error(err);
      alert("상품 저장에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex bg-white dark:bg-slate-950 overflow-auto">
      {/* HEADER */}
      <div className="fixed top-0 left-0 right-0 h-16 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between px-6 z-10 shadow-sm">
        <div className="flex items-center gap-4">
          <button onClick={onClose} className="p-2 -ml-2 rounded-full hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500">
            <X size={20} />
          </button>
          <h2 className="text-xl font-bold dark:text-white">
            {isEdit ? "상품 수정 스튜디오" : "새 상품 등록 스튜디오"}
          </h2>
        </div>
        <div className="flex gap-3">
          <button onClick={onClose} className="px-5 py-2 text-sm font-semibold text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg">
            취소
          </button>
          <button onClick={handleSubmit} disabled={saving} className="px-6 py-2 text-sm font-bold text-white bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 rounded-lg flex items-center gap-2">
            {saving ? <Loader2 size={16} className="animate-spin" /> : "저장하기"}
          </button>
        </div>
      </div>

      {/* CONTENT BUILDER */}
      <div className="pt-24 pb-12 px-6 lg:px-12 max-w-7xl mx-auto w-full flex flex-col lg:flex-row gap-8">
        
        {/* LEFT COLUMN: Main Information */}
        <div className="w-full lg:w-2/3 space-y-6">
          <div className="bg-white dark:bg-slate-900 p-6 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800">
            <h3 className="text-lg font-bold mb-4 dark:text-white">기본 정보</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-semibold text-slate-600 dark:text-slate-400 mb-1.5">상품명 (한국어)</label>
                <input value={form.kr_name} onChange={e => handleChange("kr_name", e.target.value)} className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500" placeholder="예: 프리미엄 가죽 크로스백" />
              </div>
              <div className="space-y-1.5">
                <label className="block text-sm font-semibold text-slate-600 dark:text-slate-400">간략 설명 (요약)</label>
                <input value={form.kr_description} onChange={e => handleChange("kr_description", e.target.value)} className="w-full bg-slate-50 dark:bg-slate-800 border-none rounded-lg px-4 py-2 text-sm outline-none" placeholder="고객에게 보여질 한줄 설명" />
              </div>
            </div>
          </div>

          <div className="bg-white dark:bg-slate-900 p-6 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800">
            <h3 className="text-lg font-bold mb-4 dark:text-white">이미지 (촬영 & 갤러리)</h3>
            <div {...getRootProps()} className={`border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center cursor-pointer transition ${isDragActive ? "border-blue-500 bg-blue-50 dark:bg-blue-900/20" : "border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 hover:bg-slate-100 dark:hover:bg-slate-800"}`}>
              <input {...getInputProps()} />
              <UploadCloud size={40} className="text-slate-400 mb-3" />
              <p className="text-sm font-medium text-slate-600 dark:text-slate-300">이미지를 드래그하거나 클릭하여 업로드하세요</p>
              <p className="text-xs text-slate-400 mt-1">{uploadingImage ? "업로드 중..." : "JPG, PNG 지원"}</p>
            </div>
            
            {form.images.length > 0 && (
              <div className="mt-4 grid grid-cols-4 sm:grid-cols-6 gap-3">
                {form.images.map((img: string, idx: number) => (
                  <div key={idx} className={`relative group aspect-square rounded-lg border-2 overflow-hidden ${form.ai_fitting_image_url === img ? 'border-blue-500' : 'border-slate-200 dark:border-slate-700'}`}>
                    <img src={img} alt="" className="w-full h-full object-cover" />
                    <button onClick={() => removeGalleryImage(idx)} className="absolute top-1 right-1 p-1 bg-black/50 hover:bg-red-500 rounded text-white opacity-0 group-hover:opacity-100 transition">
                      <X size={12} />
                    </button>
                    {form.ai_fitting_image_url === img && (
                      <div className="absolute bottom-0 inset-x-0 bg-blue-500 text-white text-[10px] text-center py-0.5 font-bold">대표</div>
                    )}
                    {form.ai_fitting_image_url !== img && (
                      <button onClick={() => handleChange("ai_fitting_image_url", img)} className="absolute bottom-0 inset-x-0 bg-black/50 hover:bg-blue-500 text-white text-[10px] text-center py-0.5 opacity-0 group-hover:opacity-100 transition font-bold">
                        대표로 설정
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800 flex justify-between items-center bg-slate-50 dark:bg-slate-900/50">
              <h3 className="text-lg font-bold dark:text-white flex items-center gap-2">
                <FileImage size={18} className="text-blue-500" />
                상품 상세 설명 (리치)
              </h3>
              <div className="relative">
                <input type="file" id="editor-image-upload" className="hidden" accept="image/*" onChange={insertImageToEditor} />
                <label htmlFor="editor-image-upload" className="flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-md cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-700">
                  <ImageIcon size={14} /> 이미지 삽입
                </label>
              </div>
            </div>
            
            {/* Tiptap Toolbar (Simple Custom UI) */}
            {editor && (
              <div className="flex px-4 py-2 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 gap-1">
                <button onClick={() => editor.chain().focus().toggleBold().run()} className={`p-1.5 rounded ${editor.isActive('bold') ? 'bg-slate-200 dark:bg-slate-700 font-black' : 'hover:bg-slate-100 dark:hover:bg-slate-800 font-bold'}`}>B</button>
                <button onClick={() => editor.chain().focus().toggleItalic().run()} className={`p-1.5 rounded ${editor.isActive('italic') ? 'bg-slate-200 dark:bg-slate-700 italic' : 'hover:bg-slate-100 dark:hover:bg-slate-800 italic'}`}>I</button>
                <div className="w-px h-6 bg-slate-200 dark:bg-slate-700 mx-2 self-center"></div>
                <button onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()} className={`px-2 py-1 text-sm font-bold rounded ${editor.isActive('heading', { level: 2 }) ? 'bg-slate-200 dark:bg-slate-700' : 'hover:bg-slate-100 dark:hover:bg-slate-800'}`}>H2</button>
                <button onClick={() => editor.chain().focus().toggleBulletList().run()} className={`p-1.5 rounded ${editor.isActive('bulletList') ? 'bg-slate-200 dark:bg-slate-700' : 'hover:bg-slate-100 dark:hover:bg-slate-800'}`}>• List</button>
              </div>
            )}
            
            <EditorContent editor={editor} className="bg-white dark:bg-slate-900 min-h-[400px]" />
          </div>
        </div>

        {/* RIGHT COLUMN: Settings & Meta */}
        <div className="w-full lg:w-1/3 space-y-6">
          <div className="bg-white dark:bg-slate-900 p-6 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800">
            <h3 className="text-sm font-bold text-slate-500 uppercase tracking-wider mb-4">상태 (Status)</h3>
            <select value={form.status} onChange={e => handleChange("status", e.target.value)} className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-4 py-2.5 outline-none font-semibold">
              <option value="APPROVED">승인 (판매 노출)</option>
              <option value="PENDING">대기 / 검수 중</option>
              <option value="REJECTED">비노출 (숨김처리)</option>
            </select>
          </div>

          <div className="bg-white dark:bg-slate-900 p-6 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800">
            <div className="flex items-center gap-2 mb-4 text-slate-800 dark:text-white">
              <Box size={18} />
              <h3 className="text-md font-bold">카테고리 설정</h3>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-500 mb-1">카테고리 선택</label>
                <select value={form.category_id} onChange={e => handleChange("category_id", parseInt(e.target.value))} className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500">
                  {(() => {
                    const options: React.ReactNode[] = [];
                    const parents = categories.filter(c => !c.parent_id);
                    parents.forEach(parent => {
                      options.push(
                        <option key={parent.id} value={parent.id} className="font-bold text-slate-900 dark:text-slate-100">
                          {parent.name} (대분류)
                        </option>
                      );
                      const midCats = categories.filter(c => c.parent_id === parent.id);
                      midCats.forEach(mid => {
                        options.push(
                          <option key={mid.id} value={mid.id} className="text-slate-700 dark:text-slate-300 font-semibold">
                            {"\u00A0\u00A0ㄴ "}{mid.name} (중분류)
                          </option>
                        );
                        const subCats = categories.filter(c => c.parent_id === mid.id);
                        subCats.forEach(sub => {
                          options.push(
                            <option key={sub.id} value={sub.id} className="text-slate-500 dark:text-slate-400">
                              {"\u00A0\u00A0\u00A0\u00A0ㄴ "}{sub.name}
                            </option>
                          );
                        });
                      });
                    });
                    return options;
                  })()}
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-500 mb-1 flex items-center gap-1"><Tag size={12}/> 키워드 태그</label>
                <input value={form.keywords} onChange={e => handleChange("keywords", e.target.value)} className="w-full bg-slate-50 dark:bg-slate-800 border-none rounded-lg px-4 py-2 text-sm outline-none" placeholder="쉼표(,)로 구분 (예: 프리미엄, 크로스백, 가죽)" />
                <p className="text-[10px] text-slate-400 mt-1">SEO 검색 최적화에 활용됩니다.</p>
              </div>
            </div>
          </div>

          <div className="bg-white dark:bg-slate-900 p-6 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800">
            <div className="flex items-center gap-2 mb-4 text-slate-800 dark:text-white">
              <DollarSign size={18} className="text-green-500" />
              <h3 className="text-md font-bold">가격 & 재고</h3>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-500 mb-1">정가 (Base Price)</label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 font-semibold">₩</span>
                  <input type="number" value={form.base_price} onChange={e => handleChange("base_price", parseInt(e.target.value)||0)} className="w-full bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg pl-8 pr-4 py-2 text-sm outline-none font-bold" />
                </div>
              </div>
              <div className="flex gap-3">
                <div className="flex-1">
                  <label className="block text-xs font-semibold text-slate-500 mb-1">할인가 (Sale Price)</label>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 font-semibold">₩</span>
                    <input type="number" value={form.sale_price} onChange={e => handleChange("sale_price", parseInt(e.target.value)||0)} className="w-full bg-slate-50 dark:bg-slate-800 border-none rounded-lg pl-8 pr-4 py-2 text-sm outline-none text-red-500 font-bold" />
                  </div>
                </div>
                <div className="w-16">
                  <label className="block text-xs text-center font-semibold text-slate-500 mb-1">할인율</label>
                  <div className="h-9 px-2 flex items-center justify-center bg-red-50 text-red-600 font-bold text-sm rounded-lg">
                    {discountRate}%
                  </div>
                </div>
              </div>
              
              <div className="pt-4 border-t border-slate-200 dark:border-slate-800">
                <div className="flex gap-4">
                  <div className="flex-1">
                    <label className="block text-xs font-semibold text-slate-500 mb-1">재고 수량 (Stock)</label>
                    <input type="number" value={form.stock_quantity} onChange={e => handleChange("stock_quantity", parseInt(e.target.value)||0)} className="w-full bg-slate-50 dark:bg-slate-800 border-none rounded-lg px-4 py-2 text-sm outline-none" />
                  </div>
                  <div className="flex-1">
                    <label className="block text-xs font-semibold text-slate-500 mb-1">관리번호 (SKU/코드)</label>
                    <input value={form.sku} onChange={e => handleChange("sku", e.target.value)} className="w-full bg-slate-50 dark:bg-slate-800 border-none rounded-lg px-4 py-2 text-sm outline-none" placeholder="ITM-001..." />
                  </div>
                </div>
              </div>
            </div>
          </div>
          
        </div>
      </div>
    </div>
  );
}
