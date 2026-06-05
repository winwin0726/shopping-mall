import os
for f in os.listdir('backend'):
    if f.startswith('my_style_prompt_') and f.endswith('.txt'):
        path = 'backend/' + f
        if os.path.exists(path) and os.path.getsize(path) > 0:
            with open(path, 'r', encoding='utf-8') as file:
                content = file.read()
            # Clean up unwanted parts
            content = content.replace(' / 고급고야드반지갑', '')
            content = content.replace(' / 고급샤넬반지갑', '')
            content = content.replace(' / 쇼핑백 / 영수증 / 고급고야드반지갑', '')
            content = content.replace('풀박스 + 고야드 고급 카드지갑', '풀박스')
            content = content.replace('풀박스 + 샤넬 고급 카드지갑', '풀박스')
            # Write back
            with open(path, 'w', encoding='utf-8') as file:
                file.write(content)
print("Style cleanup complete!")
