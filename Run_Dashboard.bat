@echo off
title Gonder Gebeya Pro Suite - Server
setlocal

echo ===================================================
echo   GONDER GEBEYA PRO SUITE: LAUNCHING SYSTEM...
echo ===================================================
echo.

:: Check if virtual environment exists
if not exist ".\venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment 'venv' not found!
    echo Please make sure you have installed the system correctly.
    pause
    exit /b 1
)

echo [1/2] Preparing Dashboard Interface...
:: Start the browser with an 8 second delay to allow server startup
:: This prevents the "Connection Refused" error on slow starts
start /b cmd /c "timeout /t 8 >nul && start http://127.0.0.1:8001"

echo [2/2] Starting Secure Backend Server...
echo.
echo ===================================================
echo PLEASE DO NOT CLOSE THIS WINDOW WHILE USING THE SYSTEM.
echo ===================================================
echo.

:: Start the server
.\venv\Scripts\python -m uvicorn main:app --reload --host 127.0.0.1 --port 8001
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] The server failed to start. 
    echo Please check if another instance is already running.
    pause
)
