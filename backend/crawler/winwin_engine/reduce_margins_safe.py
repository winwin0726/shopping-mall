import re

with open('web-ui/src/pages/KakaoPage.jsx', 'r', encoding='utf-8') as f:
    text = f.read()

start_idx = text.find('<div className="grid grid-cols-1 lg:grid-cols-2')
end_idx = text.find('{/* 1. 상품 리스트', start_idx)

if start_idx != -1 and end_idx != -1:
    block = text[start_idx:end_idx]
    
    # We want to replace these exact class strings:
    replacements = [
        ('gap-6', 'gap-4'),
        ('px-4 py-3', 'px-3 py-2'),
        ('p-4 flex flex-col', 'p-3 flex flex-col'),
        ('gap-4', 'gap-3'),
        ('gap-3', 'gap-2'),
        ('p-3', 'p-2'),
        ('p-6', 'p-4'),
        ('text-lg', 'text-base'),
        ('py-4', 'py-3'),
        ('px-6', 'px-4'),
        ('p-2.5', 'p-2') # Just in case it was modified before
    ]
    
    # To prevent double replacement (e.g. gap-6 -> gap-4 -> gap-3 -> gap-2), 
    # we should replace with a temporary token. But since this is simple UI classes, 
    # doing it sequentially is what caused the excessive shrink earlier.
    # Let's do it safely.
    
    def replace_safe(text, old, new):
        return text.replace(old, new)
        
    block = replace_safe(block, 'gap-6', 'gap-4')
    block = replace_safe(block, 'px-4 py-3', 'px-3 py-2')
    # careful with p-4
    block = re.sub(r'\bp-4\b', 'p-3', block)
    block = re.sub(r'\bp-6\b', 'p-4', block)
    block = re.sub(r'\bgap-4\b', 'gap-3', block)
    block = re.sub(r'\bpx-6 py-4\b', 'px-4 py-3', block)
    block = re.sub(r'\btext-lg\b', 'text-base', block)
    
    new_text = text[:start_idx] + block + text[end_idx:]
    with open('web-ui/src/pages/KakaoPage.jsx', 'w', encoding='utf-8') as f:
        f.write(new_text)
    print("SUCCESS")
else:
    print("NOT FOUND")
