@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

set ROOT=%~dp0
set BACKEND=%ROOT%backend
set FRONTEND=%ROOT%frontend
set CHAT_MODEL=qwen3:8b
set EMBED_MODEL=nomic-embed-text

echo.
echo [INFO]  Interview AI - Startup Script
echo =====================================================

:: Check Ollama
echo [INFO]  Checking Ollama...
curl -s http://localhost:11434/api/tags > nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO]  Starting Ollama...
    start /min "" ollama serve
    set OLLAMA_WAIT=0
    :WAIT_OLLAMA
    timeout /t 1 /nobreak > nul
    curl -s http://localhost:11434/api/tags > nul 2>&1
    if %errorlevel% equ 0 goto OLLAMA_OK
    set /a OLLAMA_WAIT+=1
    if !OLLAMA_WAIT! lss 15 goto WAIT_OLLAMA
    echo [ERR ]  Ollama startup timed out.
    echo [ERR ]  Please install Ollama from https://ollama.com
    pause
    exit /b 1
) else (
    echo [ OK ]  Ollama is running.
)
:OLLAMA_OK

:: Download models if missing
echo [INFO]  Checking models...

ollama list 2>nul | findstr /B "%CHAT_MODEL%" > nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO]  Downloading %CHAT_MODEL% ... (first time only, may take a few minutes)
    ollama pull %CHAT_MODEL%
    if %errorlevel% neq 0 (
        echo [ERR ]  Failed to download model. Check your network connection.
        pause
        exit /b 1
    )
    echo [ OK ]  %CHAT_MODEL% downloaded.
) else (
    echo [ OK ]  %CHAT_MODEL% already exists.
)

ollama list 2>nul | findstr /B "%EMBED_MODEL%" > nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO]  Downloading %EMBED_MODEL% ... (first time only)
    ollama pull %EMBED_MODEL%
    if %errorlevel% neq 0 (
        echo [ERR ]  Failed to download model. Check your network connection.
        pause
        exit /b 1
    )
    echo [ OK ]  %EMBED_MODEL% downloaded.
) else (
    echo [ OK ]  %EMBED_MODEL% already exists.
)

:: Start backend
echo [INFO]  Starting backend (http://localhost:8000)...
cd /d "%BACKEND%"
if not exist ".venv" (
    echo [INFO]  Creating virtual environment...
    python -m venv .venv
    .venv\Scripts\pip install -q -r requirements.txt
)
start "FastAPI Backend" /min .venv\Scripts\uvicorn main:app --host 0.0.0.0 --port 8000 --reload
echo [ OK ]  Backend started.

:: Start frontend
echo [INFO]  Starting frontend (http://localhost:5173)...
cd /d "%FRONTEND%"
if not exist "node_modules" (
    echo [INFO]  Running npm install...
    npm install --silent
)
start "Vite Frontend" /min npm run dev
echo [ OK ]  Frontend started.

:: Done
echo.
echo =====================================================
echo [ OK ]  Ready!
echo.
echo   App     : http://localhost:5173
echo   API doc : http://localhost:8000/docs
echo.
echo   Opening browser in 3 seconds...
echo =====================================================
echo.

timeout /t 3 /nobreak > nul
start http://localhost:5173

pause
