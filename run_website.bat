@echo off
echo Starting India Power Demand and Weather Platform...
cd /d "%~dp0"
start "" http://localhost:8000
if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe -m uvicorn server.main:app --port 8000
) else (
    python -m uvicorn server.main:app --port 8000
)
pause
