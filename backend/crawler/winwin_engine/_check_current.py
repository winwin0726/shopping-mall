import json
v = json.load(open(r'c:\programing\윈윈크롤러2\weishang_vendors.json','r',encoding='utf-8'))
vid = '_Zgb7eSQ-cIx3Xa9B1V50jSLkyMtFXnsI'
for i, x in enumerate(v):
    if x.get('id') == vid:
        nm = x.get('name', '?')
        pr = 'Y' if x.get('profile_rules') else 'N'
        print(f"현재 처리중: {i+1}/259번째")
        print(f"업체명: {nm}")
        print(f"이미 프로파일 있음: {pr}")
        break
