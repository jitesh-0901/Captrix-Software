# Captrix AI - PowerShell Local Server Launcher
$ErrorActionPreference = "Stop"

Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host "CAPTRIX AI - Local Server Launcher (PowerShell)" -ForegroundColor Cyan
Write-Host "==============================================================================" -ForegroundColor Cyan

$rootDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$backendDir = Join-Path $rootDir "backend"
$frontendDir = Join-Path $rootDir "frontend"
$venvPython = Join-Path $backendDir ".venv\Scripts\python.exe"

# 1. Pre-flight checks
if (-not (Test-Path $venvPython)) {
    Write-Host "[WARNING] Backend virtualenv not found in backend\.venv. Running setup.bat..." -ForegroundColor Yellow
    & (Join-Path $rootDir "setup.bat")
}

if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
    Write-Host "[INFO] Frontend node_modules not found. Installing packages..." -ForegroundColor Yellow
    Push-Location $frontendDir
    npm install
    Pop-Location
}

# 2. Launch Backend Server in new window
Write-Host "[1/3] Starting Django Backend at http://127.0.0.1:8000/ ..." -ForegroundColor Green
$backendArgs = "/k `"$venvPython`" manage.py runserver 127.0.0.1:8000"
Start-Process "cmd.exe" -ArgumentList $backendArgs -WorkingDirectory $backendDir

# 3. Launch Frontend Server in new window
Write-Host "[2/3] Starting Vite Frontend at http://localhost:3000/ ..." -ForegroundColor Green
Start-Process "cmd.exe" -ArgumentList "/k npm run dev" -WorkingDirectory $frontendDir

# 4. Wait for Backend Health Check & Open Browser
Write-Host "[3/3] Waiting for Django Backend to be ready..." -ForegroundColor Gray
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $res = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/health/" -UseBasicParsing -TimeoutSec 1
        if ($res.StatusCode -eq 200) {
            $ready = $true
            break
        }
    } catch {}
    Start-Sleep -Milliseconds 600
}
if ($ready) {
    Write-Host "Django Backend is online and healthy!" -ForegroundColor Green
} else {
    Write-Host "[WARNING] Django backend is taking longer than expected to respond." -ForegroundColor Yellow
}

Write-Host "Opening Captrix AI in your default web browser..." -ForegroundColor Cyan
Start-Process "http://localhost:3000/"

Write-Host ""
Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host "  CAPTRIX AI IS RUNNING!" -ForegroundColor Green
Write-Host "  - Frontend Web UI : http://localhost:3000/" -ForegroundColor White
Write-Host "  - Backend API     : http://127.0.0.1:8000/" -ForegroundColor White
Write-Host "  - Health Check    : http://127.0.0.1:8000/api/health/" -ForegroundColor White
Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host "Servers are running in their respective background windows." -ForegroundColor Gray
