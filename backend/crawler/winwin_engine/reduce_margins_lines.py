import os

with open('web-ui/src/pages/KakaoPage.jsx', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i in range(2010, 2400):
    if i >= len(lines): break
    
    # 1. Main Grid gaps
    lines[i] = lines[i].replace('gap-6', 'gap-2')
    lines[i] = lines[i].replace('gap-4', 'gap-2')
    lines[i] = lines[i].replace('gap-3', 'gap-1.5')
    
    # 2. Paddings
    lines[i] = lines[i].replace('p-4', 'p-3')
    lines[i] = lines[i].replace('p-6', 'p-4')
    lines[i] = lines[i].replace('p-3', 'p-2')
    lines[i] = lines[i].replace('px-4 py-3', 'px-3 py-1.5')
    lines[i] = lines[i].replace('py-3', 'py-2')
    lines[i] = lines[i].replace('py-4', 'py-2.5')
    
    # 3. Heights
    lines[i] = lines[i].replace('h-12', 'h-10')

with open('web-ui/src/pages/KakaoPage.jsx', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('SUCCESS')
