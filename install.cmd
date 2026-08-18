@echo off
REM Antigravity LSP Enforcement Kit - Windows CMD 1-Click Installer
title Antigravity LSP Enforcement Kit Installer
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Installation failed.
    pause
    exit /b %ERRORLEVEL%
)
echo.
pause
