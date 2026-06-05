import re

file_path = r'c:\programing\윈윈크롤러2\web-ui\src\pages\KakaoPage.jsx'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add import
if 'import ResizableTh' not in content:
    content = content.replace(
        '''import PostStatusBadge from '../components/PostStatusBadge';''',
        '''import PostStatusBadge from '../components/PostStatusBadge';\nimport ResizableTh from '../components/ResizableTh';'''
    )

# 2. Add colWidths state
state_code = '''  // 프로필 선택 모달 상태'''
new_state = '''  // --- 테이블 열 너비 상태 ---
  const [colWidths, setColWidths] = useState({
    colCheck: 40,
    colIndex: 48,
    colVendor: 100,
    colImage: 114,
    colTitle: 150,
    colCode: 150,
    colContent: 300,
    colCost: 80,
    colPrice: 100,
    colDate: 140,
    colManage: 80,
    colCas: 60,
    colBand: 60
  });

  const handleResize = (key, newWidth) => {
    setColWidths(prev => ({ ...prev, [key]: newWidth }));
  };

  // 프로필 선택 모달 상태'''
if 'colWidths' not in content:
    content = content.replace(state_code, new_state)

# 3. Update table tag
content = content.replace('<table className="w-full text-sm relative">', '<table className="min-w-full w-max table-fixed text-sm relative">')

# 4. Update thead
old_thead = '''              <thead className="sticky top-0 z-10 shadow-sm">
                <tr className="border-b border-border bg-[#111827] divide-x divide-gray-700">
                  <th className="px-2 py-1 text-center w-10 shrink-0">
                    <input
                      type="checkbox"
                      className="rounded border-border bg-[#111827] text-primary focus:ring-primary/50 cursor-pointer w-3.5 h-3.5"
                      checked={displayedProductRows.length > 0 && displayedProductRows.every(product => selectedProductIndices.includes(product._origIdx))}
                      onChange={handleSelectAllProducts}
                      title={productSearchText.trim() ? '검색 결과 전체 선택/해제' : '전체 선택/해제'}
                    />
                  </th>
                  <th className="px-4 py-0.5 text-center text-textMuted font-semibold w-12">#</th>
                  <th className="px-4 py-0.5 text-center text-textMuted font-semibold w-[90px]">업체명</th>
                  <th className="px-4 py-0.5 text-center text-textMuted font-semibold w-[114px]">이미지</th>
                  <th className="px-4 py-0.5 text-center text-textMuted font-semibold min-w-[100px] w-[100px]">제목</th>
                  <th className="px-4 py-0.5 text-center text-textMuted font-semibold w-28">상품코드</th>
                  <th className="px-4 py-0.5 text-center text-textMuted font-semibold w-[228px]">본문</th>
                  <th
                    className="px-4 py-0.5 text-center text-textMuted font-semibold w-[80px] cursor-pointer select-none hover:text-accentPurple transition-colors"
                    onClick={() => {
                      if (sortConfig.key === 'cost') {
                        setSortConfig({ key: 'cost', order: sortConfig.order === 'asc' ? 'desc' : 'asc' });
                      } else {
                        setSortConfig({ key: 'cost', order: 'desc' }); // Start with high to low
                      }
                    }}
                    title="원가 기준 정렬"
                  >
                    원가 {sortConfig.key === 'cost' ? (sortConfig.order === 'asc' ? '▲' : '▼') : ''}
                  </th>
                  <th className="px-4 py-0.5 text-center text-textMuted font-semibold w-[100px]">판매가</th>
                  <th
                    className="px-4 py-0.5 text-center text-textMuted font-semibold min-w-[140px] cursor-pointer select-none hover:text-accentPurple transition-colors"
                    onClick={() => {
                      if (sortConfig.key === 'date') {
                        setSortConfig({ key: 'date', order: sortConfig.order === 'asc' ? 'desc' : 'asc' });
                      } else {
                        setSortConfig({ key: 'date', order: 'asc' });
                      }
                    }}
                    title="클릭하면 정렬 순서가 바뀝니다"
                  >
                    수집일시 {sortConfig.key === 'date' ? (sortConfig.order === 'asc' ? '▲' : '▼') : ''}
                  </th>
                  <th className="px-4 py-0.5 text-center text-textMuted font-semibold w-20">관리</th>
                  <th className="px-2 py-0.5 text-center text-textMuted font-semibold w-[60px]" title="카카오스토리 업로드 상태">카스</th>
                  <th className="px-2 py-0.5 text-center text-textMuted font-semibold w-[60px]" title="네이버 밴드 업로드 상태">밴드</th>
                </tr>
              </thead>'''

new_thead = '''              <thead className="sticky top-0 z-10 shadow-sm">
                <tr className="border-b border-border bg-[#111827] divide-x divide-gray-700/50">
                  <ResizableTh width={colWidths.colCheck} onResize={(w) => handleResize('colCheck', w)} className="px-2 py-1 text-center shrink-0">
                    <input
                      type="checkbox"
                      className="rounded border-border bg-[#111827] text-primary focus:ring-primary/50 cursor-pointer w-3.5 h-3.5"
                      checked={displayedProductRows.length > 0 && displayedProductRows.every(product => selectedProductIndices.includes(product._origIdx))}
                      onChange={handleSelectAllProducts}
                      title={productSearchText.trim() ? '검색 결과 전체 선택/해제' : '전체 선택/해제'}
                    />
                  </ResizableTh>
                  <ResizableTh width={colWidths.colIndex} onResize={(w) => handleResize('colIndex', w)} className="px-2 py-0.5 text-center text-textMuted font-semibold">#</ResizableTh>
                  <ResizableTh width={colWidths.colVendor} onResize={(w) => handleResize('colVendor', w)} className="px-2 py-0.5 text-center text-textMuted font-semibold">업체명</ResizableTh>
                  <ResizableTh width={colWidths.colImage} onResize={(w) => handleResize('colImage', w)} className="px-2 py-0.5 text-center text-textMuted font-semibold">이미지</ResizableTh>
                  <ResizableTh width={colWidths.colTitle} onResize={(w) => handleResize('colTitle', w)} className="px-2 py-0.5 text-center text-textMuted font-semibold">제목</ResizableTh>
                  <ResizableTh width={colWidths.colCode} onResize={(w) => handleResize('colCode', w)} className="px-2 py-0.5 text-center text-textMuted font-semibold">상품코드</ResizableTh>
                  <ResizableTh width={colWidths.colContent} onResize={(w) => handleResize('colContent', w)} className="px-2 py-0.5 text-center text-textMuted font-semibold">본문</ResizableTh>
                  <ResizableTh
                    width={colWidths.colCost} onResize={(w) => handleResize('colCost', w)}
                    className="px-2 py-0.5 text-center text-textMuted font-semibold cursor-pointer select-none hover:text-accentPurple transition-colors"
                    onClick={() => {
                      if (sortConfig.key === 'cost') {
                        setSortConfig({ key: 'cost', order: sortConfig.order === 'asc' ? 'desc' : 'asc' });
                      } else {
                        setSortConfig({ key: 'cost', order: 'desc' });
                      }
                    }}
                    title="원가 기준 정렬"
                  >
                    원가 {sortConfig.key === 'cost' ? (sortConfig.order === 'asc' ? '▲' : '▼') : ''}
                  </ResizableTh>
                  <ResizableTh width={colWidths.colPrice} onResize={(w) => handleResize('colPrice', w)} className="px-2 py-0.5 text-center text-textMuted font-semibold">판매가</ResizableTh>
                  <ResizableTh
                    width={colWidths.colDate} onResize={(w) => handleResize('colDate', w)}
                    className="px-2 py-0.5 text-center text-textMuted font-semibold cursor-pointer select-none hover:text-accentPurple transition-colors"
                    onClick={() => {
                      if (sortConfig.key === 'date') {
                        setSortConfig({ key: 'date', order: sortConfig.order === 'asc' ? 'desc' : 'asc' });
                      } else {
                        setSortConfig({ key: 'date', order: 'asc' });
                      }
                    }}
                    title="클릭하면 정렬 순서가 바뀝니다"
                  >
                    수집일시 {sortConfig.key === 'date' ? (sortConfig.order === 'asc' ? '▲' : '▼') : ''}
                  </ResizableTh>
                  <ResizableTh width={colWidths.colManage} onResize={(w) => handleResize('colManage', w)} className="px-2 py-0.5 text-center text-textMuted font-semibold">관리</ResizableTh>
                  <ResizableTh width={colWidths.colCas} onResize={(w) => handleResize('colCas', w)} className="px-2 py-0.5 text-center text-textMuted font-semibold" title="카카오스토리 업로드 상태">카스</ResizableTh>
                  <ResizableTh width={colWidths.colBand} onResize={(w) => handleResize('colBand', w)} className="px-2 py-0.5 text-center text-textMuted font-semibold" title="네이버 밴드 업로드 상태">밴드</ResizableTh>
                </tr>
              </thead>'''
if old_thead in content:
    content = content.replace(old_thead, new_thead)
else:
    print('Failed to replace thead.')

# 5. Add divide-x divide-gray-700/50 to tbody tr
old_tbody_tr = '''className={`border-b border-border/50 transition-all duration-300 ease-out outline-none focus:bg-[#1a1f2e] focus:shadow-[inset_0_0_0_2px_#8b5cf6] relative ${selectedProductIndices.includes(index) ? 'bg-primary/10 shadow-[inset_4px_0_0_0_#8b5cf6]' : 'hover:bg-[#252f44] hover:shadow-[0_0_20px_rgba(139,92,246,0.15)] hover:z-10'}`}'''
new_tbody_tr = '''className={`border-b border-border/50 divide-x divide-gray-700/50 transition-all duration-300 ease-out outline-none focus:bg-[#1a1f2e] focus:shadow-[inset_0_0_0_2px_#8b5cf6] relative ${selectedProductIndices.includes(index) ? 'bg-primary/10 shadow-[inset_4px_0_0_0_#8b5cf6]' : 'hover:bg-[#252f44] hover:shadow-[0_0_20px_rgba(139,92,246,0.15)] hover:z-10'}`}'''
if old_tbody_tr in content:
    content = content.replace(old_tbody_tr, new_tbody_tr)
else:
    print('Failed to replace tbody tr.')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Table updated successfully!')
