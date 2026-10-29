@echo off
REM One-click start from source: creates .venv on first run, installs packages, opens the app.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo First run: creating a Python environment and installing packages. This takes a few minutes...
  python -m venv .venv || (echo Python 3.10+ is needed: https://www.python.org/downloads/ & pause & exit /b 1)
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt || (echo Package install failed. & pause & exit /b 1)
)
".venv\Scripts\python.exe" launcher.py
pause
