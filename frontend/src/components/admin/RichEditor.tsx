"use client";
import { authFetch, API_URL } from "@/lib/api";

import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { Image } from "@tiptap/extension-image";
import { Link } from "@tiptap/extension-link";
import { Underline } from "@tiptap/extension-underline";
import { TextAlign } from "@tiptap/extension-text-align";
import { TextStyle } from "@tiptap/extension-text-style";
import { Color } from "@tiptap/extension-color";
import { Highlight } from "@tiptap/extension-highlight";
import { Table } from "@tiptap/extension-table";
import { TableRow } from "@tiptap/extension-table-row";
import { TableHeader } from "@tiptap/extension-table-header";
import { TableCell } from "@tiptap/extension-table-cell";

import { Extension } from "@tiptap/core";
import { useEffect, useRef, useState } from "react";
import {
  Bold, Italic, Underline as UnderlineIcon, AlignLeft, AlignCenter, AlignRight, AlignJustify,
  Type, Palette, Highlighter, Table2, Plus, Minus, Trash2, Link2, Unlink,
  Image as ImageIcon, Undo, Redo, Heading1, Heading2, Heading3, Quote, HelpCircle,
  FilePlus, ClipboardList
} from "lucide-react";

// ─────────────────────────────────────────────────────────────────────────────
// 1. TipTap 커스텀 FontSize Extension 선언 및 TypeScript 타입 추가
// ─────────────────────────────────────────────────────────────────────────────
declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    fontSize: {
      setFontSize: (size: string) => ReturnType;
      unsetFontSize: () => ReturnType;
    };
  }
}

const FontSize = Extension.create({
  name: "fontSize",
  addOptions() {
    return {
      types: ["textStyle"],
    };
  },
  addGlobalAttributes() {
    return [
      {
        types: this.options.types,
        attributes: {
          fontSize: {
            default: null,
            parseHTML: (element) => element.style.fontSize?.replace(/px/g, ""),
            renderHTML: (attributes) => {
              if (!attributes.fontSize) {
                return {};
              }
              return {
                style: `font-size: ${attributes.fontSize}px`,
              };
            },
          },
        },
      },
    ];
  },
  addCommands() {
    return {
      setFontSize:
        (fontSize: string) =>
        ({ chain }) => {
          return chain().setMark("textStyle", { fontSize }).run();
        },
      unsetFontSize:
        () =>
        ({ chain }) => {
          return chain().setMark("textStyle", { fontSize: null }).run();
        },
    };
  },
});

// ─────────────────────────────────────────────────────────────────────────────
// 2. 메인 RichEditor 컴포넌트 구현
// ─────────────────────────────────────────────────────────────────────────────
interface RichEditorProps {
  value: string;
  onChange: (val: string) => void;
  placeholder?: string;
}

const FONT_SIZES = ["12", "14", "16", "18", "20", "24", "28", "32", "40"];
const TEXT_COLORS = [
  { name: "기본 검은색", value: "#0f172a" },
  { name: "진한 회색", value: "#475569" },
  { name: "연한 회색", value: "#94a3b8" },
  { name: "럭스 레드", value: "#ef4444" },
  { name: "럭스 블루", value: "#3b82f6" },
  { name: "에메랄드", value: "#10b981" },
  { name: "골드 옐로", value: "#f59e0b" },
  { name: "네온 퍼플", value: "#8b5cf6" },
];

const HIGHLIGHT_COLORS = [
  { name: "지우기", value: "transparent" },
  { name: "옐로 형광", value: "#fef08a" },
  { name: "그린 형광", value: "#bbf7d0" },
  { name: "레드 형광", value: "#fecaca" },
  { name: "블루 형광", value: "#bfdbfe" },
  { name: "퍼플 형광", value: "#ddd6fe" },
];

export default function RichEditor({ value, onChange, placeholder }: RichEditorProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [showColorPicker, setShowColorPicker] = useState(false);
  const [showHighlightPicker, setShowHighlightPicker] = useState(false);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        bulletList: {
          HTMLAttributes: {
            class: "list-disc pl-5 my-2 space-y-1 text-slate-700",
          },
        },
        orderedList: {
          HTMLAttributes: {
            class: "list-decimal pl-5 my-2 space-y-1 text-slate-700",
          },
        },
        blockquote: {
          HTMLAttributes: {
            class: "border-l-4 border-blue-500 bg-slate-50 pl-4 py-2 my-4 italic text-slate-600 rounded-r-lg",
          },
        },
      }),
      Underline,
      TextAlign.configure({
        types: ["heading", "paragraph"],
      }),
      TextStyle,
      FontSize,
      Color,
      Highlight.configure({
        multicolor: true,
      }),
      Table.configure({
        resizable: true,
        HTMLAttributes: {
          class: "w-full border-collapse border border-slate-200 my-4 rounded-lg overflow-hidden text-sm",
        },
      }),
      TableRow,
      TableHeader.configure({
        HTMLAttributes: {
          class: "border border-slate-200 bg-slate-50 font-bold px-3 py-2 text-left text-slate-700",
        },
      }),
      TableCell.configure({
        HTMLAttributes: {
          class: "border border-slate-200 bg-white px-3 py-2 text-slate-600",
        },
      }),
      Image.configure({
        HTMLAttributes: {
          class: "max-w-full h-auto rounded-xl my-4 border border-slate-200 block mx-auto shadow-md hover:scale-[1.01] transition-transform",
        },
      }),
      Link.configure({
        openOnClick: false,
        HTMLAttributes: {
          class: "text-blue-600 hover:text-blue-500 underline cursor-pointer font-medium",
        },
      }),
    ],
    content: value,
    immediatelyRender: false,
    onUpdate: ({ editor }) => {
      onChange(editor.getHTML());
    },
  });

  // 부모 컴포넌트로부터 들어오는 초기값 또는 동적 업데이트 바인딩
  useEffect(() => {
    if (editor && value !== editor.getHTML()) {
      editor.commands.setContent(value);
    }
  }, [value, editor]);

  if (!editor) {
    return (
      <div className="w-full h-40 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-center text-slate-400 text-xs animate-pulse">
        고성능 에디터 로딩 중...
      </div>
    );
  }

  // 이미지 업로드 처리
  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      if (!file.type.startsWith("image/")) {
        alert("이미지 파일만 업로드 가능합니다.");
        return;
      }
      setIsUploading(true);
      try {
        const formData = new FormData();
        formData.append("file", file);
        
        const res = await authFetch(`${API_URL}/api/admin/upload/`, {
          method: "POST",
          body: formData,
        });

        if (!res.ok) throw new Error("이미지 업로드 실패");
        const data = await res.json();
        
        editor.chain().focus().setImage({ src: data.url }).run();
      } catch (err: any) {
        alert(err.message);
      } finally {
        setIsUploading(false);
        e.target.value = "";
      }
    }
  };

  // 링크 설정
  const setLink = () => {
    const previousUrl = editor.getAttributes("link").href;
    const url = window.prompt("연결할 하이퍼링크 URL을 입력하세요:", previousUrl);

    if (url === null) return;

    if (url === "") {
      editor.chain().focus().extendMarkRange("link").unsetLink().run();
      return;
    }

    editor.chain().focus().extendMarkRange("link").setLink({ href: url }).run();
  };

  return (
    <div className="w-full border border-slate-200 bg-white rounded-xl overflow-hidden focus-within:border-blue-500 focus-within:shadow-lg focus-within:shadow-blue-500/5 transition-all flex flex-col relative shadow-sm">
      {/* 테이블 스타일링을 위한 인라인 스타일 인젝션 */}
      <style>{`
        .tiptap-content table {
          border-collapse: collapse;
          table-layout: fixed;
          width: 100%;
          margin: 1.5rem 0;
          overflow: hidden;
        }
        .tiptap-content td, .tiptap-content th {
          min-width: 1em;
          border: 1px solid #e2e8f0;
          padding: 8px 12px;
          vertical-align: top;
          box-sizing: border-box;
          position: relative;
        }
        .tiptap-content th {
          background-color: #f8fafc;
          font-weight: bold;
          text-align: left;
        }
        .tiptap-content .selectedCell:after {
          z-index: 2;
          position: absolute;
          content: "";
          left: 0; right: 0; top: 0; bottom: 0;
          background: rgba(59, 130, 246, 0.08);
          pointer-events: none;
        }
        .tiptap-content blockquote {
          border-left: 4px solid #3b82f6;
          padding-left: 1rem;
          margin: 1rem 0;
          font-style: italic;
          color: #475569;
        }
      `}</style>

      {/* 숨겨진 이미지 인풋 */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        onChange={handleImageUpload}
        className="hidden"
      />

      {/* ─────────────────────────────────────────────────────────────────────────────
          초고도화 툴바 레이아웃 (기능 카테고리별 정렬)
          ───────────────────────────────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-2 p-2.5 bg-slate-50 border-b border-slate-200 shrink-0">
        
        {/* 그룹 1: 텍스트 기본 서식 */}
        <div className="flex items-center bg-white p-1 rounded-lg gap-0.5 border border-slate-200 shadow-sm">
          <button
            type="button"
            onClick={() => editor.chain().focus().toggleBold().run()}
            className={`p-1.5 rounded hover:bg-slate-100 text-slate-600 transition ${editor.isActive("bold") ? "bg-slate-100 text-slate-900 font-bold" : ""}`}
            title="굵게 (Ctrl+B)"
          >
            <Bold size={14} />
          </button>
          <button
            type="button"
            onClick={() => editor.chain().focus().toggleItalic().run()}
            className={`p-1.5 rounded hover:bg-slate-100 text-slate-600 transition ${editor.isActive("italic") ? "bg-slate-100 text-slate-900" : ""}`}
            title="기울임 (Ctrl+I)"
          >
            <Italic size={14} />
          </button>
          <button
            type="button"
            onClick={() => editor.chain().focus().toggleUnderline().run()}
            className={`p-1.5 rounded hover:bg-slate-100 text-slate-600 transition ${editor.isActive("underline") ? "bg-slate-100 text-slate-900" : ""}`}
            title="밑줄 (Ctrl+U)"
          >
            <UnderlineIcon size={14} />
          </button>
          <button
            type="button"
            onClick={() => editor.chain().focus().toggleBlockquote().run()}
            className={`p-1.5 rounded hover:bg-slate-100 text-slate-600 transition ${editor.isActive("blockquote") ? "bg-slate-100 text-slate-900" : ""}`}
            title="인용구 삽입"
          >
            <Quote size={14} />
          </button>
        </div>

        {/* 그룹 2: 폰트 크기 조절 (최고의 편의성) */}
        <div className="flex items-center bg-white p-1 rounded-lg gap-1 border border-slate-200 text-xs shadow-sm">
          <Type size={13} className="text-slate-500 ml-1" />
          <select
            onChange={(e) => {
              const val = e.target.value;
              if (val === "default") {
                editor.chain().focus().unsetFontSize().run();
              } else {
                editor.chain().focus().setFontSize(val).run();
              }
            }}
            className="bg-white text-slate-700 border border-slate-200 rounded px-1 py-0.5 focus:outline-none cursor-pointer font-medium"
            title="폰트 크기 설정"
          >
            <option value="default">글자 크기 (기본)</option>
            {FONT_SIZES.map((sz) => (
              <option key={sz} value={sz}>{sz}px</option>
            ))}
          </select>
        </div>

        {/* 그룹 3: 텍스트 정렬 */}
        <div className="flex items-center bg-white p-1 rounded-lg gap-0.5 border border-slate-200 shadow-sm">
          <button
            type="button"
            onClick={() => editor.chain().focus().setTextAlign("left").run()}
            className={`p-1.5 rounded hover:bg-slate-100 text-slate-600 transition ${editor.isActive({ textAlign: "left" }) ? "bg-slate-100 text-slate-900" : ""}`}
            title="왼쪽 정렬"
          >
            <AlignLeft size={14} />
          </button>
          <button
            type="button"
            onClick={() => editor.chain().focus().setTextAlign("center").run()}
            className={`p-1.5 rounded hover:bg-slate-100 text-slate-600 transition ${editor.isActive({ textAlign: "center" }) ? "bg-slate-100 text-slate-900" : ""}`}
            title="가운데 정렬"
          >
            <AlignCenter size={14} />
          </button>
          <button
            type="button"
            onClick={() => editor.chain().focus().setTextAlign("right").run()}
            className={`p-1.5 rounded hover:bg-slate-100 text-slate-600 transition ${editor.isActive({ textAlign: "right" }) ? "bg-slate-100 text-slate-900" : ""}`}
            title="오른쪽 정렬"
          >
            <AlignRight size={14} />
          </button>
          <button
            type="button"
            onClick={() => editor.chain().focus().setTextAlign("justify").run()}
            className={`p-1.5 rounded hover:bg-slate-100 text-slate-600 transition ${editor.isActive({ textAlign: "justify" }) ? "bg-slate-100 text-slate-900" : ""}`}
            title="양방향 정렬"
          >
            <AlignJustify size={14} />
          </button>
        </div>

        {/* 그룹 4: 글자색 & 형광펜 강조 (팝업 셀렉터 기능 탑재) */}
        <div className="flex items-center bg-white p-1 rounded-lg gap-1 border border-slate-200 relative shadow-sm">
          {/* 글자색 단추 */}
          <button
            type="button"
            onClick={() => {
              setShowColorPicker(!showColorPicker);
              setShowHighlightPicker(false);
            }}
            className="p-1.5 rounded hover:bg-slate-100 text-slate-600 transition flex items-center gap-1"
            title="글자 색상 지정"
          >
            <Palette size={14} />
            <span className="text-[10px] text-slate-500 font-semibold">색상</span>
          </button>

          {/* 형광펜 단추 */}
          <button
            type="button"
            onClick={() => {
              setShowHighlightPicker(!showHighlightPicker);
              setShowColorPicker(false);
            }}
            className="p-1.5 rounded hover:bg-slate-100 text-slate-600 transition flex items-center gap-1"
            title="배경 강조색 지정"
          >
            <Highlighter size={14} />
            <span className="text-[10px] text-slate-500 font-semibold">형광</span>
          </button>

          {/* 텍스트 색상 팔레트 드롭다운 */}
          {showColorPicker && (
            <div className="absolute top-9 left-0 bg-white border border-slate-200 rounded-xl p-2.5 z-30 grid grid-cols-4 gap-1.5 shadow-xl animate-in fade-in slide-in-from-top-1 duration-200">
              {TEXT_COLORS.map((col) => (
                <button
                  key={col.name}
                  type="button"
                  onClick={() => {
                    editor.chain().focus().setColor(col.value).run();
                    setShowColorPicker(false);
                  }}
                  className="w-5 h-5 rounded-full border border-slate-200 hover:scale-110 active:scale-90 transition relative group shadow-sm"
                  style={{ backgroundColor: col.value }}
                  title={col.name}
                >
                  <span className="sr-only">{col.name}</span>
                </button>
              ))}
              <button
                type="button"
                onClick={() => {
                  editor.chain().focus().unsetColor().run();
                  setShowColorPicker(false);
                }}
                className="col-span-4 text-[10px] bg-slate-50 hover:bg-slate-100 text-slate-700 py-1.5 rounded mt-1 font-bold border border-slate-200"
              >
                기본 색상으로 재설정
              </button>
            </div>
          )}

          {/* 형광펜 강조색 팔레트 드롭다운 */}
          {showHighlightPicker && (
            <div className="absolute top-9 left-14 bg-white border border-slate-200 rounded-xl p-2.5 z-30 grid grid-cols-3 gap-1.5 shadow-xl animate-in fade-in slide-in-from-top-1 duration-200">
              {HIGHLIGHT_COLORS.map((col) => (
                <button
                  key={col.name}
                  type="button"
                  onClick={() => {
                    if (col.value === "transparent") {
                      editor.chain().focus().unsetHighlight().run();
                    } else {
                      editor.chain().focus().setHighlight({ color: col.value }).run();
                    }
                    setShowHighlightPicker(false);
                  }}
                  className="w-6 h-6 rounded border border-slate-200 hover:scale-110 active:scale-90 transition flex items-center justify-center text-[8px] font-black text-black shadow-sm"
                  style={{ 
                    backgroundColor: col.value === "transparent" ? "#f1f5f9" : col.value, 
                    color: col.value === "transparent" ? "#475569" : "#000000" 
                  }}
                  title={col.name}
                >
                  {col.value === "transparent" ? "X" : "A"}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* 그룹 5: 제목 (H1 ~ H3) */}
        <div className="flex items-center bg-white p-1 rounded-lg gap-0.5 border border-slate-200 shadow-sm">
          <button
            type="button"
            onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
            className={`p-1.5 rounded hover:bg-slate-100 text-[10px] text-slate-600 font-bold transition ${editor.isActive("heading", { level: 1 }) ? "bg-slate-100 text-slate-900 font-bold" : ""}`}
            title="대제목 (H1)"
          >
            H1
          </button>
          <button
            type="button"
            onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
            className={`p-1.5 rounded hover:bg-slate-100 text-[10px] text-slate-600 font-bold transition ${editor.isActive("heading", { level: 2 }) ? "bg-slate-100 text-slate-900 font-bold" : ""}`}
            title="중제목 (H2)"
          >
            H2
          </button>
          <button
            type="button"
            onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
            className={`p-1.5 rounded hover:bg-slate-100 text-[10px] text-slate-600 font-bold transition ${editor.isActive("heading", { level: 3 }) ? "bg-slate-100 text-slate-900 font-bold" : ""}`}
            title="소제목 (H3)"
          >
            H3
          </button>
        </div>

        {/* 그룹 6: 하이퍼링크 & 이미지 추가 */}
        <div className="flex items-center bg-white p-1 rounded-lg gap-0.5 border border-slate-200 shadow-sm">
          <button
            type="button"
            onClick={setLink}
            className={`p-1.5 rounded hover:bg-slate-100 text-slate-600 transition ${editor.isActive("link") ? "bg-slate-100 text-blue-600" : ""}`}
            title="링크 걸기"
          >
            <Link2 size={14} />
          </button>
          {editor.isActive("link") && (
            <button
              type="button"
              onClick={() => editor.chain().focus().unsetLink().run()}
              className="p-1.5 rounded hover:bg-slate-100 text-red-600 transition"
              title="링크 해제"
            >
              <Unlink size={14} />
            </button>
          )}
          <button
            type="button"
            onClick={() => !isUploading && fileInputRef.current?.click()}
            className="p-1.5 rounded hover:bg-slate-100 text-slate-600 transition flex items-center gap-1"
            title="이미지 파일 직접 업로드 삽입"
            disabled={isUploading}
          >
            <ImageIcon size={14} />
          </button>
        </div>

        {/* 그룹 7: 스마트 표(Table) 삽입 및 편집기 기능 (업계 최고의 스펙 요약용) */}
        <div className="flex items-center bg-white p-1 rounded-lg gap-1 border border-blue-500/20 shadow-sm">
          <button
            type="button"
            onClick={() => editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()}
            className="p-1.5 bg-blue-50 hover:bg-blue-100 text-blue-600 rounded transition flex items-center gap-1 text-[10px] font-bold shadow-sm"
            title="3x3 표(Table) 삽입"
          >
            <Table2 size={13} />
            <span>표 삽입</span>
          </button>

          {/* 표 내부 포커싱 상태일 때 편집 도구 추가 노출 */}
          {editor.isActive("table") && (
            <div className="flex items-center gap-0.5 border-l border-slate-200 pl-1.5 ml-0.5">
              <button
                type="button"
                onClick={() => editor.chain().focus().addRowAfter().run()}
                className="p-1.5 hover:bg-slate-50 text-emerald-600 rounded transition"
                title="아래에 행 추가"
              >
                <Plus size={12} />
                <span className="text-[8px] font-bold ml-0.5">행</span>
              </button>
              <button
                type="button"
                onClick={() => editor.chain().focus().addColumnAfter().run()}
                className="p-1.5 hover:bg-slate-50 text-emerald-600 rounded transition"
                title="우측에 열 추가"
              >
                <Plus size={12} />
                <span className="text-[8px] font-bold ml-0.5">열</span>
              </button>
              <button
                type="button"
                onClick={() => editor.chain().focus().deleteRow().run()}
                className="p-1.5 hover:bg-slate-50 text-red-600 rounded transition"
                title="현재 행 삭제"
              >
                <Minus size={12} />
                <span className="text-[8px] font-bold ml-0.5">행</span>
              </button>
              <button
                type="button"
                onClick={() => editor.chain().focus().deleteColumn().run()}
                className="p-1.5 hover:bg-slate-50 text-red-600 rounded transition"
                title="현재 열 삭제"
              >
                <Minus size={12} />
                <span className="text-[8px] font-bold ml-0.5">열</span>
              </button>
              <button
                type="button"
                onClick={() => editor.chain().focus().deleteTable().run()}
                className="p-1.5 bg-red-50 hover:bg-red-100 text-red-600 rounded transition font-semibold"
                title="표 삭제"
              >
                <Trash2 size={12} />
              </button>
            </div>
          )}
        </div>

        {/* 그룹 8: 히스토리 백업 (실행 취소 / 다시 실행) */}
        <div className="flex items-center bg-white p-1 rounded-lg gap-0.5 border border-slate-200 ml-auto shadow-sm">
          <button
            type="button"
            onClick={() => editor.chain().focus().undo().run()}
            disabled={!editor.can().undo()}
            className="p-1.5 rounded hover:bg-slate-100 text-slate-600 disabled:opacity-30 disabled:hover:bg-transparent transition"
            title="실행 취소 (Ctrl+Z)"
          >
            <Undo size={14} />
          </button>
          <button
            type="button"
            onClick={() => editor.chain().focus().redo().run()}
            disabled={!editor.can().redo()}
            className="p-1.5 rounded hover:bg-slate-100 text-slate-600 disabled:opacity-30 disabled:hover:bg-transparent transition"
            title="다시 실행 (Ctrl+Y)"
          >
            <Redo size={14} />
          </button>
        </div>

      </div>

      {/* ─────────────────────────────────────────────────────────────────────────────
          에디터 바디 (수려한 스타일링 적용)
          ───────────────────────────────────────────────────────────────────────────── */}
      <div className="p-5 flex-1 min-h-[220px] max-h-[350px] overflow-y-auto bg-white text-slate-900 text-sm focus:outline-none">
        <EditorContent
          editor={editor}
          className="tiptap-content prose prose-sm focus:outline-none max-w-none min-h-[180px] leading-relaxed text-slate-800"
        />
      </div>
    </div>
  );
}
