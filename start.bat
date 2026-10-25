@echo off
setlocal EnableDelayedExpansion
title Captrix AI - Local Launcher

echo ==============================================================================
echo CAPTRIX AI - Automated Accounting Review ^& CA Audit Platform
echo ==============================================================================
echo.

set "ROOT_DIR=%~dp0"
set "BACKEND_DIR=%ROOT_DIR%backend"
set "FRONTEND_DIR=%ROOT_DIR%frontend"
set "VENV_PYTHON=%BACKEND_DIR%\.venv\Scripts\python.exe"

:: 1. Verify Python Virtual Environment
if not exist "!VENV_PYTHON!" (
    echo [WARNING] Backend virtual environment not found in backend\.venv.
    echo Running automated setup first...
    echo.
    call "%ROOT_DIR%setup.bat"
    if !errorlevel! neq 0 (
        echo [ERROR] Setup failed. Please check the error above.
        pause
        exit /b 1
    )
)

:: 2. Verify Frontend node_modules
if not exist "!FRONTEND_DIR!\node_modules" (
    echo [WARNING] Frontend node_modules not found. Installing packages...
    pushd "!FRONTEND_DIR!"
    call npm install
    popd
)

echo [1/3] Starting Django Backend at http://127.0.0.1:8000/ ...
pushd "!BACKEND_DIR!"
start "Captrix AI - Backend Server" cmd /k ""!VENV_PYTHON!" manage.py runserver 127.0.0.1:8000"
popd

echo [2/3] Starting Vite Frontend at http://localhost:3000/ ...
pushd "!FRONTEND_DIR!"
start "Captrix AI - Frontend Server" cmd /k "npm run dev"
popd

echo [3/3] Waiting for Django Backend to be ready...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ready=$false; for($i=0; $i -lt 30; $i++) { try { $r=Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/health/' -UseBasicParsing -TimeoutSec 1; if($r.StatusCode -eq 200) { $ready=$true; break; } } catch {}; Start-Sleep -Milliseconds 600 }; if($ready) { Write-Host 'Backend is ready!' -ForegroundColor Green } else { Write-Host 'Warning: Backend is taking longer than usual to respond.' -ForegroundColor Yellow }"

echo.
echo Opening Captrix AI in your default web browser...
start http://localhost:3000/

echo.
echo ==============================================================================
echo  CAPTRIX AI IS RUNNING!
echo ==============================================================================
echo  - Frontend Web UI : http://localhost:3000/
echo  - Backend API     : http://127.0.0.1:8000/
echo  - Health Check    : http://127.0.0.1:8000/api/health/
echo ==============================================================================
echo Both backend and frontend servers are active in separate console windows.
echo Keep this window open or press any key to close this launcher.
echo (The server windows will stay running until you close them).
echo ==============================================================================
pause
