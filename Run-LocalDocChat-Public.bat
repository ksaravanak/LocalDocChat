@echo off
cd /d "%~dp0"

if not exist ".env" copy /Y ".env.example" ".env"

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  python -m venv .venv
  call .venv\Scripts\activate.bat
  pip install -r requirements.txt
) else (
  call .venv\Scripts\activate.bat
)

echo.
echo ============================================
echo  LocalDocChat - PUBLIC MODE
echo ============================================
echo.
echo Requires Ollama running locally on this PC.
echo Wait for the https://....trycloudflare.com URL below.
echo Set APP_PASSWORD in .env before sharing the link!
echo.

.venv\Scripts\python.exe run_public.py
pause
