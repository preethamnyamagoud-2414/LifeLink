@echo off
title LifeLink - Smart Blood Donor Portal
echo ==================================================================
echo   Starting LifeLink Local Server...
echo   Web Portal:   http://localhost:5000/
echo   Admin Portal: http://localhost:5000/admin/login
echo.
echo   Administrator sign-in:
echo     Email:    preethamnyamagoud@gmail.com
echo     Password: LifeLink@2026!
echo.
echo   Data is saved in: %~dp0data\lifelink-data.json
echo   Location features need the site opened from http://localhost
echo ==================================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0serve.ps1" -Port 5000
pause
