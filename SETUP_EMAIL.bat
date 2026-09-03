@echo off
REM ===================================================================
REM  DigiSafe - turn on real email
REM
REM  Double-click this file. It asks a few questions and sets up
REM  sending, so verification codes reach people's real inboxes
REM  instead of being printed in the server window.
REM
REM  Your password is typed into THIS window and saved to a file
REM  called .env on this computer. It is never uploaded anywhere,
REM  and .env is excluded from git so it cannot be committed.
REM ===================================================================

cd /d "%~dp0"
title DigiSafe - Email Setup

echo.
echo  ==========================================================
echo   Before you start, you need a Gmail App Password.
echo.
echo   Your normal Google password will NOT work - Google
echo   refuses it from applications.
echo.
echo   1. Open  https://myaccount.google.com/security
echo      and switch ON 2-Step Verification.
echo.
echo   2. Open  https://myaccount.google.com/apppasswords
echo      Type the name  DigiSafe  and click Create.
echo.
echo   3. Copy the 16 characters it shows you.
echo      It is shown ONCE. If you lose it, delete it and
echo      make another.
echo.
echo   Have that ready, then continue.
echo  ==========================================================
echo.
pause

echo.
python tools\setup_email.py

echo.
echo  ==========================================================
echo   Finished. If it said SUCCESS, check that inbox - and
echo   look in SPAM too. If it landed in spam, mark it
echo   "not spam" now, before you show anyone.
echo.
echo   If it failed, the reason is printed above.
echo  ==========================================================
echo.
pause
