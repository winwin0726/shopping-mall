@echo off
echo ============================================
echo   AI Virtual Try-On Shopping Mall Startup
echo ============================================
echo.

echo [1/2] Starting FastAPI Backend on Port 8002...
start "FastAPI Backend (8002)" /d "%~dp0" backend\venv\Scripts\python.exe -m uvicorn backend.main:app --port 8002

ping 127.0.0.1 -n 4 >nul

echo [2/2] Starting Next.js Frontend on Port 3000...
start "Next.js Frontend (3000)" /d "%~dp0frontend" npm run dev

echo.
echo ============================================
echo   Server processes launched successfully.
echo   - Backend API Docs: http://localhost:8002/docs
echo   - Shopping Mall UI: http://localhost:3000
============================================
echo.
