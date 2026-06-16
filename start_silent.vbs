Set objShell = CreateObject("WScript.Shell")
objShell.Run "cmd /c cd /d C:\Users\I605232\projects\Aiden_AI && py -m uvicorn app.main:app --host 127.0.0.1 --port 8001 >> server.log 2>&1", 0, False