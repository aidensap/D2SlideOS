@echo off
cd /d "C:\Users\I605232\projects\Aiden_AI"
py -m uvicorn app.main:app --host 0.0.0.0 --port 8001