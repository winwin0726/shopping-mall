import re

file_path = r'c:\programing\윈윈크롤러2\web-ui\src\pages\KakaoPage.jsx'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# thead tr
content = content.replace(
    '<tr className="border-b border-border bg-[#111827]">',
    '<tr className="border-b border-border bg-[#111827] divide-x divide-gray-700">'
)

# tbody tr
old_tr = r'''<tr
                      key={index}
                      tabIndex={0}
                      className={`border-b border-border transition-colors outline-none focus:bg-gray-800 ${'''

new_tr = '''<tr
                      key={index}
                      tabIndex={0}
                      className={`border-b border-border divide-x divide-gray-700 transition-colors outline-none focus:bg-gray-800 ${'''

content = re.sub(old_tr, new_tr, content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Table borders added!')
