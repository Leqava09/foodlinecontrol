@echo off
REM Quick SSH connection to cPanel server
REM Double-click to connect, or run from command line

powershell.exe -ExecutionPolicy Bypass -File "%~dp0connect.ps1" %*
