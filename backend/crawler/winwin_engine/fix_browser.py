import os
f = r'd:\안티그래비티\winwin크롤러2\backend\platforms\weishang\crawler.py'
with open(f, 'r', encoding='utf-8') as file:
    content = file.read()

content = content.replace(
    '_viewports = [{"width": 1536, "height": 864}, {"width": 1440, "height": 900}, {"width": 1920, "height": 1080}]\n                _vp = _rnd.choice(_viewports)',
    '_vp = {"width": 800, "height": 700}'
)

content = content.replace(
    '_launch_args.append(f"--window-size={_vp[\'width\']},{_vp[\'height\']}")',
    '_launch_args.extend([f"--window-size={_vp[\'width\']},{_vp[\'height\']}", "--window-position=0,0"])'
)

with open(f, 'w', encoding='utf-8') as file:
    file.write(content)
print("Done")
