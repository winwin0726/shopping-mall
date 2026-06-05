filepath = 'd:/안티그래비티/winwin크롤러2/backend/weishang_crawler.py'
with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

# clear out lines 610-613
for i in range(610, 614):
    lines[i] = '\n'

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(lines)