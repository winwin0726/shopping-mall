Set WshShell = CreateObject("WScript.Shell")
WshShell.Environment("PROCESS")("PYTHONUTF8") = "1"
WshShell.Run "python main_web.py", 0, False
