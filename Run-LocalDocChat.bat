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
echo Starting LocalDocChat at http://127.0.0.1:8090
echo Requires Ollama running with qwen2.5:7b-instruct + nomic-embed-text
echo Press Ctrl+C to stop.
echo.

python -m uvicorn app.main:app --host 127.0.0.1 --port 8090 --reload
