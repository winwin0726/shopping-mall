"""KakaoPage.jsx useEffect 삽입 스크립트"""
path = r'd:\안티그래비티\winwin크롤러2\web-ui\src\pages\KakaoPage.jsx'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

effect_code = """
  // 백업 모달 키보드 네비게이션
  useEffect(() => {
    if (!backupInfoModal?.data) return;
    const handleKeyDown = (e) => {
      if (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'TEXTAREA') return;

      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        const rows = Array.from(document.querySelectorAll('.backup-row'));
        const activeIdx = rows.indexOf(document.activeElement);
        
        if (activeIdx !== -1) {
          e.preventDefault();
          const nextIdx = e.key === 'ArrowDown' ? activeIdx + 1 : activeIdx - 1;
          if (rows[nextIdx]) {
            rows[nextIdx].focus();
          }
        } else if (rows.length > 0 && e.key === 'ArrowDown') {
          e.preventDefault();
          rows[0].focus();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [backupInfoModal]);
"""

for i, line in enumerate(lines):
    if 'const [backupInfoModal, setBackupInfoModal] = useState(null);' in line:
        lines.insert(i+1, effect_code)
        break

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(lines)
print("SUCCESS - useEffect injected")
