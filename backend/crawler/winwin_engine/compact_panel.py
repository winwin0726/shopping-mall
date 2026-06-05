import re

file_path = r'c:\programing\윈윈크롤러2\web-ui\src\pages\KakaoPage.jsx'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the layout
old_block = r'''          {/\* === 일괄 편집 패널 === \*/}
          \{showBulkEditPanel && selectedProductIndices\.length > 0 && \(
            <div className="mt-4 p-4 border-t border-border bg-\[#0f141e\] animate-in fade-in slide-in-from-top-1">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/\* 1\. 찾기 및 바꾸기 \*/}
                <div className="bg-\[#111827\] border border-border p-4 rounded-lg space-y-3">
                  <label className="text-sm font-semibold text-textMuted flex items-center gap-1">
                    🔍 찾기 및 바꾸기
                  </label>
                  <div className="flex flex-col sm:flex-row items-center gap-1">
                    <input
                      value=\{bulkFindText\}
                      onChange=\{\(e\) => setBulkFindText\(e\.target\.value\)\}
                      className="w-full bg-\[#0f141e\] border border-border rounded-lg px-3 py-1 text-sm text-textMain outline-none focus:border-primary"
                      placeholder="찾을 텍스트"
                    />
                    <ArrowRight className="w-4 h-4 text-textMuted hidden sm:block" />
                    <input
                      value=\{bulkReplaceText\}
                      onChange=\{\(e\) => setBulkReplaceText\(e\.target\.value\)\}
                      className="w-full bg-\[#0f141e\] border border-border rounded-lg px-3 py-1 text-sm text-textMain outline-none focus:border-primary"
                      placeholder="바꿀 텍스트"
                    />
                    <button
                      onClick=\{handleBulkFindAndReplace\}
                      className="w-full sm:w-auto bg-primary/20 hover:bg-primary text-primary hover:text-white border border-primary/50 text-sm font-bold px-2 py-1 rounded-lg transition-colors whitespace-nowrap min-w-\[90px\]"
                    >
                      바꾸기
                    </button>
                  </div>
                </div>

                {/\* 2\. 상/하단 올스킨 삽입 \*/}
                <div className="bg-\[#111827\] border border-border p-4 rounded-lg space-y-3">
                  <label className="text-sm font-semibold text-textMuted flex items-center gap-1">
                    📝 상/하단 올스킨 삽입
                  </label>
                  <div className="flex gap-1">
                    <textarea
                      value=\{bulkTopInsertText\}
                      onChange=\{\(e\) => setBulkTopInsertText\(e\.target\.value\)\}
                      rows=\{1\}
                      className="flex-1 bg-\[#0f141e\] border border-border rounded-lg px-3 py-1 text-sm text-textMain outline-none focus:border-primary resize-y"
                      placeholder="본문 맨 위에 추가할 내용"
                    />
                    <button
                      onClick=\{handleBulkInsertTop\}
                      className="bg-primary/20 hover:bg-primary text-primary hover:text-white border border-primary/50 text-sm font-bold px-4 rounded-lg transition-colors whitespace-nowrap min-w-\[90px\]"
                    >
                      상단 삽입
                    </button>
                  </div>
                  <div className="flex gap-1">
                    <textarea
                      value=\{bulkBottomInsertText\}
                      onChange=\{\(e\) => setBulkBottomInsertText\(e\.target\.value\)\}
                      rows=\{1\}
                      className="flex-1 bg-\[#0f141e\] border border-border rounded-lg px-3 py-1 text-sm text-textMain outline-none focus:border-primary resize-y"
                      placeholder="본문 맨 아래에 추가할 내용"
                    />
                    <button
                      onClick=\{handleBulkInsertBottom\}
                      className="bg-primary/20 hover:bg-primary text-primary hover:text-white border border-primary/50 text-sm font-bold px-4 rounded-lg transition-colors whitespace-nowrap min-w-\[90px\]"
                    >
                      하단 삽입
                    </button>
                  </div>
                </div>

                {/\* 3\. 💰 일괄 가격 조정 \*/}
                <div className="bg-\[#111827\] border border-border p-4 rounded-lg space-y-3 md:col-span-2">
                  <label className="text-sm font-semibold text-textMuted flex items-center gap-2">
                    <span>💰 일괄 가격 조정</span>
                    <select 
                      value=\{bulkPriceTarget\} 
                      onChange=\{\(e\) => setBulkPriceTarget\(e\.target\.value\)\}
                      className="bg-\[#1f2937\] border border-border rounded text-xs px-2 py-0\.5 outline-none cursor-pointer text-white ml-2"
                    >
                      <option value="sale_price">판매가\(원\) 일괄수정</option>
                      <option value="price_input">원가\(위안\) 일괄수정 \(판매가 자동재계산\)</option>
                    </select>
                  </label>
                  <div className="flex flex-col sm:flex-row items-stretch gap-1">
                    {/\* 모드 선택 버튼 \*/}
                    <div className="flex rounded-lg overflow-hidden border border-border flex-shrink-0">
                      <button
                        onClick=\{\(\) => setBulkPriceMode\('add'\)\}
                        className=\{`px-3 py-1 text-xs sm:text-sm font-bold transition-colors \$\{
                          bulkPriceMode === 'add'
                            \? 'bg-emerald-500/30 text-emerald-400 border-r border-emerald-500/50'
                            : 'bg-\[#0f141e\] text-textMuted hover:bg-white/5 border-r border-border'
                        \}`}
                      >
                        ＋ 더하기
                      </button>
                      <button
                        onClick=\{\(\) => setBulkPriceMode\('subtract'\)\}
                        className=\{`px-3 py-1 text-xs sm:text-sm font-bold transition-colors \$\{
                          bulkPriceMode === 'subtract'
                            \? 'bg-rose-500/30 text-rose-400 border-r border-rose-500/50'
                            : 'bg-\[#0f141e\] text-textMuted hover:bg-white/5 border-r border-border'
                        \}`}
                      >
                        － 빼기
                      </button>
                      <button
                        onClick=\{\(\) => setBulkPriceMode\('set'\)\}
                        className=\{`px-3 py-1 text-xs sm:text-sm font-bold transition-colors \$\{
                          bulkPriceMode === 'set'
                            \? 'bg-amber-500/30 text-amber-400'
                            : 'bg-\[#0f141e\] text-textMuted hover:bg-white/5'
                        \}`}
                      >
                        전체 지정
                      </button>
                    </div>
                    {/\* 금액 입력 \*/}
                    <div className="flex items-center gap-1 flex-1">
                      <div className="relative flex-1">
                        <input
                          type="number"
                          value=\{bulkPriceAmount\}
                          onChange=\{\(e\) => setBulkPriceAmount\(e\.target\.value\)\}
                          className="w-full bg-\[#0f141e\] border border-border rounded-lg px-3 py-1 pr-10 text-sm text-textMain outline-none focus:border-primary text-right"
                          placeholder="금액 입력"
                        />
                        <span className="absolute right-3 top-1/2 -translate-y-1/2 text-textMuted text-xs">원</span>
                      </div>
                      {/\* 일괄 수정 적용 버튼 \*/}
                      <button
                        onClick=\{handleBulkPriceUpdate\}
                        className=\{`px-4 py-1 text-sm font-bold rounded-lg transition-colors whitespace-nowrap \$\{
                          bulkPriceMode === 'add'
                            \? 'bg-emerald-500/20 hover:bg-emerald-500 text-emerald-400 hover:text-white border border-emerald-500/50'
                            : bulkPriceMode === 'subtract'
                            \? 'bg-rose-500/20 hover:bg-rose-500 text-rose-400 hover:text-white border border-rose-500/50'
                            : 'bg-amber-500/20 hover:bg-amber-500 text-amber-400 hover:text-white border border-amber-500/50'
                        \}`}
                      >
                        \{bulkPriceMode === 'add' \? '＋ 일괄 인상' : bulkPriceMode === 'subtract' \? '－ 일괄 인하' : '일괄 지정'\}
                      </button>
                    </div>
                  </div>
                  <div className="text-xs text-textMuted flex items-center gap-1">
                    선택된 <span className="text-white font-bold">\{selectedProductIndices\.length\}</span>개 상품의 
                    <span className="text-white font-bold ml-1">
                      \{bulkPriceTarget === 'sale_price' \? '판매가' : '원가'\}
                    </span>를 
                    <span className=\{`font-bold ml-1 \$\{
                      bulkPriceMode === 'add' \? 'text-emerald-400' : bulkPriceMode === 'subtract' \? 'text-rose-400' : 'text-amber-400'
                    \}`\}>
                      \{bulkPriceMode === 'add' \? '\+' : bulkPriceMode === 'subtract' \? '-' : ''\}\{bulkPriceAmount\}
                      \{bulkPriceTarget === 'sale_price' \? '원' : '위안'\}
                    </span>
                    \{bulkPriceMode === 'add' \? ' 인상' : bulkPriceMode === 'subtract' \? ' 인하' : '으로 지정'\} 합니다\.
                  </div>
                </div>
              </div>
            </div>
          \)}'''

new_block = '''          {/* === 일괄 편집 패널 === */}
          {showBulkEditPanel && selectedProductIndices.length > 0 && (
            <div className="mt-2 p-2 border-t border-border bg-[#0f141e] animate-in fade-in slide-in-from-top-1">
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-2">
                
                {/* 1. 찾기 및 바꾸기 */}
                <div className="bg-[#111827] border border-border p-2 rounded-lg flex flex-col justify-center space-y-1.5">
                  <label className="text-xs font-semibold text-textMuted flex items-center gap-1">
                    🔍 찾기 및 바꾸기
                  </label>
                  <div className="flex items-center gap-1">
                    <input
                      value={bulkFindText}
                      onChange={(e) => setBulkFindText(e.target.value)}
                      className="w-full bg-[#0f141e] border border-border rounded px-2 py-0.5 text-xs text-textMain outline-none focus:border-primary"
                      placeholder="찾을 텍스트"
                    />
                    <ArrowRight className="w-3 h-3 text-textMuted flex-shrink-0" />
                    <input
                      value={bulkReplaceText}
                      onChange={(e) => setBulkReplaceText(e.target.value)}
                      className="w-full bg-[#0f141e] border border-border rounded px-2 py-0.5 text-xs text-textMain outline-none focus:border-primary"
                      placeholder="바꿀 텍스트"
                    />
                    <button
                      onClick={handleBulkFindAndReplace}
                      className="bg-primary/20 hover:bg-primary text-primary hover:text-white border border-primary/50 text-xs font-bold px-2 py-0.5 rounded transition-colors whitespace-nowrap min-w-[50px]"
                    >
                      바꾸기
                    </button>
                  </div>
                </div>

                {/* 2. 상/하단 올스킨 삽입 */}
                <div className="bg-[#111827] border border-border p-2 rounded-lg flex flex-col justify-center space-y-1.5">
                  <label className="text-xs font-semibold text-textMuted flex items-center gap-1">
                    📝 상/하단 올스킨 삽입
                  </label>
                  <div className="flex flex-col xl:flex-row gap-1">
                    <div className="flex gap-1 w-full">
                      <input
                        value={bulkTopInsertText}
                        onChange={(e) => setBulkTopInsertText(e.target.value)}
                        className="w-full bg-[#0f141e] border border-border rounded px-2 py-0.5 text-xs text-textMain outline-none focus:border-primary"
                        placeholder="상단 추가 내용"
                      />
                      <button
                        onClick={handleBulkInsertTop}
                        className="bg-primary/20 hover:bg-primary text-primary hover:text-white border border-primary/50 text-xs font-bold px-2 py-0.5 rounded transition-colors whitespace-nowrap min-w-[60px]"
                      >
                        상단 삽입
                      </button>
                    </div>
                    <div className="flex gap-1 w-full">
                      <input
                        value={bulkBottomInsertText}
                        onChange={(e) => setBulkBottomInsertText(e.target.value)}
                        className="w-full bg-[#0f141e] border border-border rounded px-2 py-0.5 text-xs text-textMain outline-none focus:border-primary"
                        placeholder="하단 추가 내용"
                      />
                      <button
                        onClick={handleBulkInsertBottom}
                        className="bg-primary/20 hover:bg-primary text-primary hover:text-white border border-primary/50 text-xs font-bold px-2 py-0.5 rounded transition-colors whitespace-nowrap min-w-[60px]"
                      >
                        하단 삽입
                      </button>
                    </div>
                  </div>
                </div>

                {/* 3. 💰 일괄 가격 조정 */}
                <div className="bg-[#111827] border border-border p-2 rounded-lg flex flex-col justify-center space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-textMuted flex items-center gap-1">
                      <span>💰 가격 조정</span>
                    </label>
                    <select 
                      value={bulkPriceTarget} 
                      onChange={(e) => setBulkPriceTarget(e.target.value)}
                      className="bg-[#1f2937] border border-border rounded text-[10px] px-1 py-0.5 outline-none cursor-pointer text-white"
                    >
                      <option value="sale_price">판매가(원) 일괄수정</option>
                      <option value="price_input">원가(위안) 일괄수정</option>
                    </select>
                  </div>
                  
                  <div className="flex items-stretch gap-1">
                    <div className="flex rounded overflow-hidden border border-border flex-shrink-0">
                      <button onClick={() => setBulkPriceMode('add')} className={`px-2 py-0.5 text-[10px] font-bold transition-colors ${bulkPriceMode === 'add' ? 'bg-emerald-500/30 text-emerald-400 border-r border-emerald-500/50' : 'bg-[#0f141e] text-textMuted hover:bg-white/5 border-r border-border'}`}>＋</button>
                      <button onClick={() => setBulkPriceMode('subtract')} className={`px-2 py-0.5 text-[10px] font-bold transition-colors ${bulkPriceMode === 'subtract' ? 'bg-rose-500/30 text-rose-400 border-r border-rose-500/50' : 'bg-[#0f141e] text-textMuted hover:bg-white/5 border-r border-border'}`}>－</button>
                      <button onClick={() => setBulkPriceMode('set')} className={`px-2 py-0.5 text-[10px] font-bold transition-colors ${bulkPriceMode === 'set' ? 'bg-amber-500/30 text-amber-400' : 'bg-[#0f141e] text-textMuted hover:bg-white/5'}`}>지정</button>
                    </div>
                    
                    <div className="relative flex-1">
                      <input type="number" value={bulkPriceAmount} onChange={(e) => setBulkPriceAmount(e.target.value)} className="w-full bg-[#0f141e] border border-border rounded px-2 py-0.5 pr-6 text-xs text-textMain outline-none focus:border-primary text-right" placeholder="금액" />
                      <span className="absolute right-1.5 top-1/2 -translate-y-1/2 text-textMuted text-[10px]">원</span>
                    </div>
                    
                    <button onClick={handleBulkPriceUpdate} className={`px-2 py-0.5 text-xs font-bold rounded transition-colors whitespace-nowrap ${bulkPriceMode === 'add' ? 'bg-emerald-500/20 hover:bg-emerald-500 text-emerald-400 hover:text-white border border-emerald-500/50' : bulkPriceMode === 'subtract' ? 'bg-rose-500/20 hover:bg-rose-500 text-rose-400 hover:text-white border border-rose-500/50' : 'bg-amber-500/20 hover:bg-amber-500 text-amber-400 hover:text-white border border-amber-500/50'}`}>
                      적용
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}'''

new_content = re.sub(old_block, new_block, content, flags=re.DOTALL)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_content)

if new_block in new_content:
    print("Panel compacted successfully!")
else:
    print("Regex match failed.")
