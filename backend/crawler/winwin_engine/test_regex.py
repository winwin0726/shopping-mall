import re

text = '🌟39 MON# 26春夏 男装高端梭织/风衣'
text2 = '双面穿🌟42 PRD# 26春夏 男装高端梭织/风衣'

def test(text):
    _price_matches = list(re.finditer(r'(¥|元|块|价)[ \t]*([\d\.,]+)|[pPwWqQ][ \t]*(\d+)', text))
    if not _price_matches:
        _price_matches = list(re.finditer(r'(?:^|\s|[^A-Za-z0-9])(\d{2,4})(?:$|\s|[^A-Za-z0-9])', text))
    res = []
    for m in _price_matches:
        res.append((m.group(0), re.findall(r'\d+', m.group(0))))
    return res

with open('c:/programing/윈윈크롤러2/out.txt', 'w', encoding='utf-8') as f:
    f.write(str(test(text)) + '\n')
    f.write(str(test(text2)) + '\n')
