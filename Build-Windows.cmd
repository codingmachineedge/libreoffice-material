@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0bin\Build-Windows.ps1" %*
exit /b %ERRORLEVEL%
