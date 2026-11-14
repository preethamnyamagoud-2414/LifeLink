@echo off
title LifeLink — Initialize Administrator Account
echo ==================================================================
echo   LifeLink Secure Administrator Provisioning Utility
echo ==================================================================
python "%~dp0init_admin.py"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] Python execution returned code %ERRORLEVEL%.
    echo     Running PowerShell provisioning fallback...
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0init_admin.ps1"
)
pause