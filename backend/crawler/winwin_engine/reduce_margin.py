import re

with open('web-ui/src/pages/KakaoPage.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

start_token = '{/* =====================\n            1. 가져오기 (크롤링) 설정'
end_token = '{/* =====================\n            3. 검색 및 필터'

parts = content.split(start_token)
if len(parts) == 2:
    sub_parts = parts[1].split(end_token)
    if len(sub_parts) == 2:
        section = sub_parts[0]
        
        # aggressively replace margins and paddings
        section = section.replace('gap-1', 'gap-0.5')
        section = section.replace('p-1', 'p-0.5')
        section = section.replace('px-2 py-1', 'px-1.5 py-0.5')
        section = section.replace('py-1 ', 'py-0.5 ')
        section = section.replace('py-1"', 'py-0.5"')
        section = section.replace('py-1.5', 'py-1')
        section = section.replace('pt-1', 'pt-0.5')
        section = section.replace('mt-1', 'mt-0')
        section = section.replace('text-sm', 'text-xs')
        section = section.replace('text-base', 'text-sm')
        
        # reconstruct the file
        new_content = parts[0] + start_token + section + end_token + sub_parts[1]
        
        with open('web-ui/src/pages/KakaoPage.jsx', 'w', encoding='utf-8') as f:
            f.write(new_content)
        print('Aggressive UI minification applied successfully.')
    else:
        print('Could not find end token.')
else:
    print('Could not find start token.')
