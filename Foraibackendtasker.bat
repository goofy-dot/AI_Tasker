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
if errorlevel 1 goto :error

echo Installing Python packages (first run may take a few minutes)...
python -m pip install --upgrade pip
if errorlevel 1 goto :error
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

echo.
echo Checking that Ollama is running...
ollama list >nul 2>nul
if errorlevel 1 (
  echo Ollama did not respond. Start the Ollama application and run this file again.
  pause
  exit /b 1
)

rem Read the settings that the launcher itself needs from the .env file.
rem app.py and browser_agent.py also load the same file directly.
for /f "tokens=1,* delims==" %%A in ('python -c "from dotenv import load_dotenv; import os; load_dotenv(); print('BROWSER_AGENT_MODEL='+os.getenv('BROWSER_AGENT_MODEL','phi3')); print('BROWSER_AGENT_BROWSER='+os.getenv('BROWSER_AGENT_BROWSER','auto')); print('PORT='+os.getenv('PORT','5000')); print('BROWSERAI_INVITE_CODES='+os.getenv('BROWSERAI_INVITE_CODES',''))"') do set "%%A=%%B"
if not defined BROWSER_AGENT_MODEL set "BROWSER_AGENT_MODEL=phi3"
if not defined BROWSER_AGENT_BROWSER set "BROWSER_AGENT_BROWSER=auto"
if not defined PORT set "PORT=5000"

echo.
echo Automation browser preference: %BROWSER_AGENT_BROWSER%
echo Checking for the AI model %BROWSER_AGENT_MODEL% ...
ollama list | findstr /i /c:"%BROWSER_AGENT_MODEL%" >nul
if errorlevel 1 (
  echo Model not found. Downloading %BROWSER_AGENT_MODEL% (this can take a while)...
  ollama pull "%BROWSER_AGENT_MODEL%"
  if errorlevel 1 goto :error
)

echo.
echo ================================================
echo BrowserAI is ready to start.
echo Dashboard: http://127.0.0.1:%PORT%
echo Invitation code: %BROWSERAI_INVITE_CODES%
echo You can change settings in the .env file (restart BrowserAI after editing).
echo Keep this window open while using BrowserAI.
echo Press Ctrl+C here to stop the local server.
echo ================================================
echo.

python -c "from dotenv import load_dotenv; import os; load_dotenv(); raise SystemExit(0 if os.getenv('BROWSERAI_ADMIN_PASSWORD') else 1)"
if not errorlevel 1 (
  python app.py
) else (
  rem PowerShell collects the password as a SecureString so keystrokes are not
  rem echoed in the console. It supplies the password only to the Python child.
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$secure = Read-Host 'Create an admin password (input is hidden)' -AsSecureString; while ($secure.Length -eq 0) { Write-Host 'Password cannot be blank.'; $secure = Read-Host 'Create an admin password (input is hidden)' -AsSecureString }; $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure); try { $env:BROWSERAI_ADMIN_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr); & '.venv\Scripts\python.exe' 'app.py'; exit $LASTEXITCODE } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }"
)

pause
exit /b 0

:error
echo.
echo Setup failed. Read the error above, fix the issue, and run this file again.
pause
exit /b 1
