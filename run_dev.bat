@echo off
cd /d %~dp0
set "PATH=C:\Program Files\nodejs;%PATH%"
start "Probably High-Value API" cmd /k "cd /d %~dp0 && .\.venv\Scripts\python.exe -m uvicorn api.main:app --reload --port 8000"
start "Probably High-Value Web Dev" cmd /k "cd /d %~dp0\web && set PATH=C:\Program Files\nodejs;%PATH% && npm run dev"
start "" http://localhost:5173
