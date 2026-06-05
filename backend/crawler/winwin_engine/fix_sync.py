import codecs
import os
import json

path = 'd:/안티그래비티/winwin크롤러2/backend/platforms/weishang/crawler.py'
with codecs.open(path, 'r', 'utf-8') as f:
    lines = f.readlines()

out = []
skip = False
for i, line in enumerate(lines):
    if 'vendors = {}' in line and 'extracted_data' in lines[i+1]:
        skip = True
        out.append('                # 기존 저장된 업체 목록(AI 속성 보존) 읽어오기\n')
        out.append('                vendor_file = "weishang_vendors.json"\n')
        out.append('                existing_vendors = {}\n')
        out.append('                try:\n')
        out.append('                    if os.path.exists(vendor_file):\n')
        out.append('                        with open(vendor_file, "r", encoding="utf-8") as f:\n')
        out.append('                            for v in json.load(f):\n')
        out.append('                                if "id" in v:\n')
        out.append('                                    existing_vendors[v["id"]] = v\n')
        out.append('                except Exception as e:\n')
        out.append('                    self.add_log(f"⚠️ 기존 업체 목록 읽기 실패: {e}", "WARNING")\n\n')
        out.append('                new_add_count = 0\n')
        out.append('                for item in extracted_data:\n')
        out.append('                    vendor_id = item["id"]\n')
        out.append('                    if vendor_id in existing_vendors:\n')
        out.append('                        existing_vendors[vendor_id]["name"] = item["name"][:30]\n')
        out.append('                        existing_vendors[vendor_id]["url"] = f"https://www.szwego.com/static/index.html?t=1712852296766#/shop_detail/{vendor_id}"\n')
        out.append('                    else:\n')
        out.append('                        existing_vendors[vendor_id] = {\n')
        out.append('                            "id": vendor_id,\n')
        out.append('                            "name": item["name"][:30],\n')
        out.append('                            "url": f"https://www.szwego.com/static/index.html?t=1712852296766#/shop_detail/{vendor_id}"\n')
        out.append('                        }\n')
        out.append('                        new_add_count += 1\n\n')
        out.append('                vendor_list = list(existing_vendors.values())\n')
        out.append('                self.add_log(f"✅ 총 {len(vendor_list)}개의 업체 정보를 추출했습니다.", "INFO")\n')
        out.append('                if new_add_count > 0:\n')
        out.append('                    self.add_log(f"🌟 기존 AI 분석 정보를 보존하며, 새로운 업체 {new_add_count}개를 추가했습니다.", "INFO")\n')
        out.append('                else:\n')
        out.append('                    self.add_log("💡 새로 추가된 업체가 없습니다. 기존 AI 분석 정보가 안전하게 보존되었습니다.", "INFO")\n\n')
        out.append('                with open(vendor_file, "w", encoding="utf-8") as f:\n')
        out.append('                    json.dump(vendor_list, f, ensure_ascii=False, indent=2)\n\n')
        out.append('                return vendor_list\n')
        continue
    if skip:
        if 'return vendor_list' in line:
            skip = False
        continue
    out.append(line)

with codecs.open(path, 'w', 'utf-8') as f:
    f.writelines(out)

print("Done")
