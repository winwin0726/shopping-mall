import os

page_path = 'web-ui/src/pages/KakaoPage.jsx'
modal_path = 'web-ui/src/components/AiAnalysisModal.jsx'

with open(page_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

modal_content = [
    "import React from 'react';\n",
    "import { Cpu, X, FileText, ChevronDown, ChevronRight } from 'lucide-react';\n\n",
    "export default function AiAnalysisModal({\n",
    "  showAnalysisModal,\n",
    "  setShowAnalysisModal,\n",
    "  analysisCategory,\n",
    "  analysisLoading,\n",
    "  analysisData,\n",
    "  showRawText,\n",
    "  setShowRawText\n",
    "}) {\n",
    "  if (!showAnalysisModal) return null;\n\n",
    "  return (\n"
]

# 2958번 인덱스는 2959번째 줄 ({showAnalysisModal && ()
# 3208번 인덱스는 3209번째 줄 ()}) 이므로 2959~3208 인덱스를 순회하며 복사
for i in range(2959, 3208):
    modal_content.append(lines[i])

modal_content.append("  );\n}\n")

with open(modal_path, 'w', encoding='utf-8') as f:
    f.writelines(modal_content)

new_lines = []
skip = False

for i, l in enumerate(lines):
    if l.startswith("import ProfileModal"):
        new_lines.append(l)
        new_lines.append("import AiAnalysisModal from '../components/AiAnalysisModal';\n")
        continue
        
    if i == 2958:
        skip = True
        new_lines.append('      {/* 분석 결과 뷰어 모달 — 시각적 대시보드 */}\n')
        new_lines.append('      <AiAnalysisModal\n')
        new_lines.append('        showAnalysisModal={showAnalysisModal}\n')
        new_lines.append('        setShowAnalysisModal={setShowAnalysisModal}\n')
        new_lines.append('        analysisCategory={analysisCategory}\n')
        new_lines.append('        analysisLoading={analysisLoading}\n')
        new_lines.append('        analysisData={analysisData}\n')
        new_lines.append('        showRawText={showRawText}\n')
        new_lines.append('        setShowRawText={setShowRawText}\n')
        new_lines.append('      />\n')
        continue
        
    if skip and i == 3208:
        skip = False
        continue
        
    if not skip:
        new_lines.append(l)

with open(page_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print("Done!")
