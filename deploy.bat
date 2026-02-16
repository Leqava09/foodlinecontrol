@echo off
REM Quick deployment to cPanel
REM Double-click to deploy latest changes

echo ========================================
echo Deploying to cPanel Server
echo ========================================
echo.

powershell.exe -ExecutionPolicy Bypass -File "%~dp0connect.ps1" -Deploy

echo.
pause
