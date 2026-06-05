import re

with open('web-ui/src/pages/KakaoPage.jsx', 'rb') as f:
    text = f.read().decode('utf-8')

# We want to replace paddings in the pipeline section.
top_section_start = text.find('<div className="grid grid-cols-1 md:grid-cols-2 gap-6">')
if top_section_start == -1:
    top_section_start = text.find('<div className="grid grid-cols-1 lg:grid-cols-2 gap-6">')

if top_section_start != -1:
    # Find the end of this grid by looking for the next main section
    top_section_end = text.find('{/* =====================', top_section_start + 10)
    
    if top_section_end != -1:
        top_section = text[top_section_start:top_section_end]
        new_top_section = top_section.replace('gap-6', 'gap-4')
        new_top_section = new_top_section.replace('px-4 py-3', 'px-3 py-2')
        new_top_section = new_top_section.replace('p-4 flex flex-col', 'p-3 flex flex-col')
        new_top_section = new_top_section.replace('gap-4', 'gap-3')
        new_top_section = new_top_section.replace('gap-3', 'gap-2')
        new_top_section = new_top_section.replace('p-3', 'p-2.5')
        new_top_section = new_top_section.replace('p-6', 'p-4')
        new_top_section = new_top_section.replace('text-lg', 'text-base')
        new_top_section = new_top_section.replace('py-4', 'py-3')
        new_top_section = new_top_section.replace('px-6', 'px-4')
        
        text = text[:top_section_start] + new_top_section + text[top_section_end:]

        with open('web-ui/src/pages/KakaoPage.jsx', 'wb') as f:
            f.write(text.encode('utf-8'))
        print('SUCCESS')
    else:
        print('END NOT FOUND')
else:
    print('START NOT FOUND')
