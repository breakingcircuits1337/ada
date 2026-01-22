@echo off
echo ===================================================
echo Starting L.I.S.A. System (Life Integrated System Architecture)
echo ===================================================

echo [1/3] Starting Local LiveKit Server (Docker)...
docker-compose up -d
if %ERRORLEVEL% NEQ 0 (
    echo Error starting Docker. Is Docker Desktop running?
    pause
    exit /b
)

echo [2/3] Starting API Server & Command Center...
start "L.I.S.A API Server" cmd /k "venv\Scripts\activate && uvicorn server:app --reload"

echo [3/3] Starting L.I.S.A Agent...
start "L.I.S.A Voice Agent" cmd /k "venv\Scripts\activate && python ADA/ADA_LiveKit.py dev"

echo ===================================================
echo All systems launched!
echo - Command Center: http://localhost:8000/command-center
echo - LiveKit Dashboard: http://localhost:7880
echo - API Docs: http://localhost:8000/docs
echo ===================================================
