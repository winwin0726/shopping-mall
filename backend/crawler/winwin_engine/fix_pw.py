import re

file_path = r'c:\programing\윈윈크롤러2\backend\crawler_engine.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

email_old = r'''                email_field\.clear\(\)
                # 사람처럼 타이핑
                for char in credentials\['login_id'\]:
                    email_field\.send_keys\(char\)
                    time\.sleep\(0\.05\)
                time\.sleep\(0\.5\)
                email_field\.send_keys\(Keys\.ENTER\)'''

email_new = '''                # React/Vue 완벽한 텍스트 지우기
                email_field.click()
                time.sleep(0.1)
                email_field.send_keys(Keys.CONTROL + "a")
                time.sleep(0.1)
                email_field.send_keys(Keys.BACKSPACE)
                time.sleep(0.1)
                email_field.send_keys(credentials['login_id'])
                time.sleep(0.5)
                email_field.send_keys(Keys.ENTER)'''

content = re.sub(email_old, email_new, content)

pw_old = r'''                pw_field\.clear\(\)
                # 사람처럼 타이핑
                for char in credentials\['login_pw'\]:
                    pw_field\.send_keys\(char\)
                    time\.sleep\(0\.05\)
                time\.sleep\(0\.5\)
                pw_field\.send_keys\(Keys\.ENTER\)'''

pw_new = '''                # 무한 입력 버그 방지
                pw_field.click()
                time.sleep(0.1)
                pw_field.send_keys(Keys.CONTROL + "a")
                time.sleep(0.1)
                pw_field.send_keys(Keys.BACKSPACE)
                time.sleep(0.1)
                pw_field.send_keys(credentials['login_pw'])
                time.sleep(0.5)
                pw_field.send_keys(Keys.ENTER)'''

content = re.sub(pw_old, pw_new, content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Login fix applied!')
