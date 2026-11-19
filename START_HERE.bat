@echo off
echo ========================================
echo  Taskloom SDLC Platform Startup
echo ========================================
echo.
echo Starting backend server...
start "Taskloom Backend" cmd /k "python main.py"

echo Waiting for backend to initialize...
timeout /t 5 /nobreak >nul

echo.
echo Starting frontend development server...
start "Taskloom Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo ========================================
echo  Platform is starting...
echo ========================================
echo.
echo Backend API:    http://localhost:8000
echo Frontend App:   http://localhost:5173
echo API Docs:       http://localhost:8000/docs
echo.
echo To access SDLC Dashboard, click on "پلتفرم SDLC" in the navigation menu
echo.
pause