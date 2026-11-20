@echo off
setlocal
title Taskloom
cd /d "%~dp0"

rem Usage:
rem   TASKLOOM.bat          build the UI and serve everything from the backend on http://127.0.0.1:8003
rem   TASKLOOM.bat dev      backend on :8003 + Vite dev server with hot reload on http://localhost:5173
rem   Extra arguments (normal mode) are passed to main.py, e.g. TASKLOOM.bat --port 8010

where python >nul 2>nul || (echo [!] Python was not found on PATH. & exit /b 1)
where npm >nul 2>nul || (echo [!] Node.js / npm was not found on PATH. & exit /b 1)

curl -s -o nul --max-time 3 http://localhost:11434/api/tags
if errorlevel 1 echo [!] Ollama is not responding on http://localhost:11434 - SDLC agents will fail until you run "ollama serve".

if not exist "frontend\node_modules" (
    echo Installing frontend dependencies...
    pushd frontend
    call npm install
    if errorlevel 1 (popd & echo [!] npm install failed. & exit /b 1)
    popd
)

if /i "%~1"=="dev" goto dev

echo Building the dashboard...
pushd frontend
call npm run build
if errorlevel 1 (popd & echo [!] Frontend build failed. & exit /b 1)
popd

python main.py %*
exit /b %errorlevel%

:dev
start "Taskloom Backend" cmd /k python main.py --no-browser
rem Vite answers /api calls with "500" when the backend is not up, so wait for it first.
set /a tries=0
:wait_backend
curl -s -o nul --max-time 2 http://127.0.0.1:8003/api/health && goto backend_ready
set /a tries+=1
if %tries% geq 30 (
    echo [!] The backend did not start on http://127.0.0.1:8003 - check the "Taskloom Backend" window for the error.
    echo     Until it runs, every /api request from the dashboard fails with 500.
    goto start_vite
)
timeout /t 1 /nobreak >nul
goto wait_backend
:backend_ready
echo Backend is ready on http://127.0.0.1:8003
:start_vite
pushd frontend
call npm run dev
popd
exit /b 0
