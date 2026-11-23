@echo off
setlocal
cd /d "%~dp0"

echo ================================================
echo          BrowserAI - Local Windows Setup
echo ================================================
echo.

where py >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.10 or newer from https://www.python.org/downloads/
  echo During installation, enable "Add Python to PATH".
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating Python virtual environment...
  py -3 -m venv .venv
  if errorlevel 1 goto :error
)

call ".venv\Scripts\activate.bat"
echo Installing Python packages (first run may take a few minutes)...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 goto :error

where ollama >nul 2>nul
if errorlevel 1 (
  echo.
  echo Ollama was not found. Install it from https://ollama.com/download/windows
  echo Then close this window, install Ollama, and run this file again.
  pause
  exit /b 1
)

set "BROWSERAI_INVITE_CODES=browserai-local"
set "BROWSERAI_AGENT_ENABLED=true"
if not defined BROWSER_AGENT_MODEL set "BROWSER_AGENT_MODEL=phi3"
if not defined BROWSER_AGENT_HEADLESS set "BROWSER_AGENT_HEADLESS=0"
if not defined BROWSERAI_ADMIN_PASSWORD call :ask_password

echo.
echo Checking for the AI model %BROWSER_AGENT_MODEL% ...
ollama list | findstr /i "%BROWSER_AGENT_MODEL%" >nul
if errorlevel 1 (
  echo Model not found. Downloading %BROWSER_AGENT_MODEL% (this can take a while)...
  ollama pull %BROWSER_AGENT_MODEL%
  if errorlevel 1 goto :error
)

echo.
echo BrowserAI is starting at http://127.0.0.1:5000
echo Invitation code: browserai-local
echo Keep this window open while using BrowserAI.
echo Press Ctrl+C here to stop the local server.
echo.
python app.py
pause
exit /b 0

:ask_password
echo.
set /p "BROWSERAI_ADMIN_PASSWORD=Create an admin password for this local dashboard: "
if not defined BROWSERAI_ADMIN_PASSWORD goto ask_password
goto :eof

:error
echo.
echo Setup failed. Read the error above, fix the missing dependency, and run this file again.
pause
exit /b 1
