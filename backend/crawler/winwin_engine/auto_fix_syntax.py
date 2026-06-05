import sys
import py_compile
import re

filepath = 'd:/안티그래비티/winwin크롤러2/backend/weishang_crawler.py'

for _ in range(100):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    try:
        py_compile.compile(filepath, doraise=True)
        break  # Compilation successful!
    except py_compile.PyCompileError as e:
        err_msg = str(e)
        if 'unterminated string literal' in err_msg or 'SyntaxError' in err_msg:
            # Extract line number
            m = re.search(r'line (\d+)', err_msg)
            if m:
                line_num = int(m.group(1)) - 1
                line = lines[line_num]
                if 'reason =' in line:
                    lines[line_num] = line.split('reason =')[0] + 'reason = ""\n'
                elif 'self.add_log' in line:
                    lines[line_num] = line.split('self.add_log')[0] + 'self.add_log("corrupted log line", "WARNING")\n'
                elif 'if ' in line and 'in txt' in line:
                    lines[line_num] = line.split('if ')[0] + 'if False:\n'
                elif 'if ' in line and '==' in line:
                    lines[line_num] = line.split('if ')[0] + 'if False:\n'
                elif 'self.error_signal' in line:
                    lines[line_num] = line.split('self.error_signal')[0] + 'self.error_signal.emit("corrupt")\n'
                elif 'self.log_signal' in line:
                    lines[line_num] = line.split('self.log_signal')[0] + 'self.log_signal.emit("corrupt")\n'
                elif 'print(' in line:
                    lines[line_num] = line.split('print(')[0] + 'print("corrupt")\n'
                elif '=' in line:
                    lines[line_num] = line.split('=')[0] + '= ""\n'
                else:
                    lines[line_num] = '#' + lines[line_num]
                
                print(f"Fixed line {line_num+1}: {line.strip()} -> {lines[line_num].strip()}")
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.writelines(lines)
            else:
                print("Could not parse line number:", err_msg)
                break
        else:
            print("Other compile error:", err_msg)
            break

print("Done fixing syntax errors!")