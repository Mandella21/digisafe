@echo off
REM ===================================================================
REM  DigiSafe - put the site live on a public HTTPS address
REM
REM  Double-click this file. It starts the app and opens a Cloudflare
REM  tunnel, then prints a public https://....trycloudflare.com link
REM  that anyone on the internet can open.
REM
REM  Keep this window OPEN for as long as you want the site reachable.
REM  Closing it takes the site offline. The link changes each time you
REM  run this, so copy the new one whenever you restart.
REM ===================================================================

cd /d "%~dp0"
title DigiSafe - Live Site

echo.
echo  ==========================================================
echo   DigiSafe - starting live site
echo  ==========================================================
echo.

if not exist "tools\cloudflared.exe" (
    echo  ERROR: tools\cloudflared.exe is missing.
    echo.
    echo  Download it from:
    echo    https://github.com/cloudflare/cloudflared/releases/latest
    echo  Pick "cloudflared-windows-amd64.exe", rename it to
    echo  cloudflared.exe, and put it in the "tools" folder.
    echo.
    pause
    exit /b 1
)

echo  [1/3] Starting the DigiSafe server...
REM Bound to 0.0.0.0, not 127.0.0.1, so the site is reachable two ways at once:
REM through the public tunnel below, and directly from a phone on the same
REM Wi-Fi at http://<this-PC-IP>:8000. 127.0.0.1 would allow neither.
REM
REM The server window is NOT minimised: with no mail server configured, the
REM verification codes are printed there, and a minimised window hides them.
start "DigiSafe Server" cmd /c "python -m uvicorn main:app --host 0.0.0.0 --port 8000"

echo  [2/3] Waiting for the server to come up...
REM The ML models load at startup, so give it a moment.
timeout /t 15 /nobreak >nul

echo  [3/3] Opening the public tunnel...
echo.
echo  ==========================================================
echo   Look for the https://....trycloudflare.com link below.
echo   That is your public website address - share that one.
echo.
echo   Keep this window open. Press Ctrl+C to take the site down.
echo.
echo   Verification codes: if you have not set up a mail server
echo   see EMAIL_SETUP.md - sign-up codes are printed in the
echo   separate "DigiSafe Server" window, not in this one.
echo  ==========================================================
echo.

tools\cloudflared.exe tunnel --url http://127.0.0.1:8000 --no-autoupdate

echo.
echo  Tunnel closed - the site is now offline.
pause
