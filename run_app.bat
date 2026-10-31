@echo off
rem Production launcher: always rebuild the React bundle, then serve it with FastAPI on :8000.
cd /d %~dp0
set "PATH=C:\Program Files\nodejs;%PATH%"

rem Refuse to start if something is already on :8000. Otherwise the new server fails to bind
rem and the browser silently shows whatever old process is still running there.
netstat -ano | findstr /R /C:":8000 .*LISTENING" >nul
if not errorlevel 1 (
  echo Port 8000 is already in use. Close the old server window first:
  netstat -ano | findstr /R /C:":8000 .*LISTENING"
  pause
  exit /b 1
)

pushd web
if not exist node_modules call npm ci
rem Always rebuild so web\dist never lags behind web\src.
call npm run build
if errorlevel 1 (
  echo Frontend build failed; not starting the server.
  popd
  pause
  exit /b 1
)
popd

call .venv\Scripts\activate.bat
start "" http://localhost:8000
.\.venv\Scripts\python.exe -m uvicorn api.main:app --port 8000
