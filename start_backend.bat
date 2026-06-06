@echo off
cd /d "%~dp0backend"

if not exist ".env" (
    echo Copying .env.example to .env...
    copy .env.example .env
    echo IMPORTANT: Edit backend\.env and add your ANTHROPIC_API_KEY before continuing.
    pause
    exit /b 1
)

if not exist "venv" (
    echo Creating Python virtual environment...
    python -m venv venv
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing dependencies...
pip install -r requirements.txt --quiet

if not exist "theater.db" (
    echo Seeding database...
    python seed_data.py
)

echo.
echo ============================================================
echo  THEATER Backend starting on http://localhost:8000
echo  API docs: http://localhost:8000/docs
echo ============================================================
echo.

uvicorn main:app --host 0.0.0.0 --port 8000 --reload
