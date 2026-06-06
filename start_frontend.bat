@echo off
cd /d "%~dp0frontend"

if not exist "node_modules" (
    echo Installing npm dependencies...
    npm install
)

echo.
echo ============================================================
echo  THEATER Frontend starting on http://localhost:3000
echo ============================================================
echo.

npm run dev
