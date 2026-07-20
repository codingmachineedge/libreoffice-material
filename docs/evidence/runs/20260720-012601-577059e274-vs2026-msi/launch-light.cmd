@echo off
setlocal DisableDelayedExpansion
set "RUN_ID=20260720-012601-577059e274-vs2026-msi"
set "RUN_ROOT=%LOCALAPPDATA%\Temp\LibreOfficeMaterialQA\%RUN_ID%"
set "PROFILE_PATH=%RUN_ROOT%\profile"
set "PROFILE_URL=%PROFILE_PATH:\=/%"
set "PAYLOAD_ROOT=%USERPROFILE%\lo-material-vs2026-577059e27\msi-check\20260720-012452-4022690-LibreOfficeDev_27.2.0.0.alpha0_Win_x86-64-65318bd180824353b4d8c28b53ebeb86"
set "VCL_DRAW_WIDGETS_FROM_FILE=1"
set "VCL_FILE_WIDGET_THEME=material"
set "SAL_LOG=+WARN.vcl.gdi"
"%PAYLOAD_ROOT%\program\soffice.exe" ^
  -env:UserInstallation=file:///%PROFILE_URL% ^
  --nologo --norestore --quickstart=no --language=en-US ^
  --pidfile="%RUN_ROOT%\soffice.pid" ^
  --accept=pipe,name=LibreOfficeMaterialQA-%RUN_ID%;urp ^
  1>"%RUN_ROOT%\soffice.stdout.log" 2>"%RUN_ROOT%\soffice.stderr.log"
exit /b %ERRORLEVEL%
