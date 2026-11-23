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
echo Keep this window open while using BrowserAI.
echo Press Ctrl+C here to stop the local server.
echo ================================================
echo.

if defined BROWSERAI_ADMIN_PASSWORD (
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
