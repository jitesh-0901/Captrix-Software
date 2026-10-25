@echo off
setlocal EnableDelayedExpansion
title Captrix AI - Setup

echo ==============================================================================
echo CAPTRIX AI — Automated Environment Setup
echo ==============================================================================
echo.

set "ROOT_DIR=%~dp0"
set "BACKEND_DIR=%ROOT_DIR%backend"
set "FRONTEND_DIR=%ROOT_DIR%frontend"
set "VENV_DIR=%BACKEND_DIR%\.venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"

:: 1. Detect Python or UV
set "BASE_PYTHON="

:: Check if standard python is in PATH
python --version >nul 2>&1
if !errorlevel! equ 0 (
    set "BASE_PYTHON=python"
    goto :PYTHON_FOUND
)

:: Check py launcher
py -3 --version >nul 2>&1
if !errorlevel! equ 0 (
    set "BASE_PYTHON=py -3"
    goto :PYTHON_FOUND
)

:: Check uv
where uv >nul 2>&1
if !errorlevel! equ 0 (
    set "HAS_UV=1"
) else if exist "%USERPROFILE%\.local\bin\uv.exe" (
    set "HAS_UV=1"
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)

:: Check uv python cache
if exist "%APPDATA%\uv\python\cpython-3.12-windows-x86_64-none\python.exe" (
    set "BASE_PYTHON=%APPDATA%\uv\python\cpython-3.12-windows-x86_64-none\python.exe"
    goto :PYTHON_FOUND
)

:: Check typical Windows AppData Python
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "BASE_PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    goto :PYTHON_FOUND
)

:PYTHON_FOUND
if not defined BASE_PYTHON (
    if defined HAS_UV (
        echo [INFO] Found uv package manager.
    ) else (
        echo [ERROR] Python 3.11+ was not found on your system.
        echo Please install Python 3.12 from https://www.python.org/downloads/
        pause
        exit /b 1
    )
)

:: 2. Create Virtual Environment if not exists
if not exist "!VENV_PYTHON!" (
    echo [1/4] Creating backend virtual environment in backend\.venv...
    if defined HAS_UV (
        if defined BASE_PYTHON (
            uv venv "!VENV_DIR!" --python "!BASE_PYTHON!"
        ) else (
            uv venv "!VENV_DIR!" --python 3.12
        )
    ) else (
        !BASE_PYTHON! -m venv "!VENV_DIR!"
    )
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo [1/4] Virtual environment already exists in backend\.venv.
)

:: 3. Install Python Dependencies
echo [2/4] Installing backend dependencies...
if defined HAS_UV (
    uv pip install -r "!BACKEND_DIR!\requirements.txt" --python "!VENV_PYTHON!"
) else (
    "!VENV_PYTHON!" -m pip install --upgrade pip
    "!VENV_PYTHON!" -m pip install -r "!BACKEND_DIR!\requirements.txt"
)
if !errorlevel! neq 0 (
    echo [ERROR] Failed to install backend dependencies.
    pause
    exit /b 1
)

:: 4. Run Django Migrations
echo [3/4] Running Django database migrations...
pushd "!BACKEND_DIR!"
"!VENV_PYTHON!" manage.py migrate
if !errorlevel! neq 0 (
    echo [ERROR] Failed to apply database migrations.
    popd
    pause
    exit /b 1
)
popd

:: 5. Install Frontend Dependencies
echo [4/5] Installing frontend dependencies via npm...
pushd "!FRONTEND_DIR!"
call npm install
if !errorlevel! neq 0 (
    echo [ERROR] Failed to install frontend dependencies.
    popd
    pause
    exit /b 1
)
popd

:: 6. Verify and Generate Sample Test Workbooks
echo [5/5] Generating baseline sample audit workbooks...
pushd "!BACKEND_DIR!"
"!VENV_PYTHON!" create_sample_files.py
if !errorlevel! neq 0 (
    echo [WARNING] Sample file generation encountered an issue, but setup can continue.
)
popd

echo.
echo ==============================================================================
echo Setup completed successfully!
echo You can now launch the application using start.bat
echo ==============================================================================
