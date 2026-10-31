@echo off
cd /d %~dp0
set "PATH=C:\Program Files\nodejs;%PATH%"
if not exist web\dist\index.html (
  pushd web
  call npm ci
  call npm run build
  popd
)
call .venv\Scripts\activate.bat
start "" http://localhost:8000
.\.venv\Scripts\python.exe -m uvicorn api.main:app --port 8000
