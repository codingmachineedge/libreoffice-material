@echo off
setlocal DisableDelayedExpansion
set "VCL_DRAW_WIDGETS_FROM_FILE=1"
set "VCL_FILE_WIDGET_THEME=material"
set "SAL_SKIA=raster"
set "SAL_DISABLEGL=1"
set "SAL_LOG=+WARN.vcl.gdi"
"C:\Users\cntow\lo-material-vs2026-577059e27\msi-check\20260720-021814-9378266-fbba560e2-restart-suppression\program\soffice.exe" -env:UserInstallation=file:///C:/Users/cntow/AppData/Local/Temp/LibreOfficeMaterialQA/20260720-022159-fbba560e27-vs2026-msi-raster-restart-suppression/profile --nologo --norestore --quickstart=no --language=en-US --pidfile="C:\Users\cntow\AppData\Local\Temp\LibreOfficeMaterialQA\20260720-022159-fbba560e27-vs2026-msi-raster-restart-suppression\soffice.pid" --accept=pipe,name=LibreOfficeMaterialQA-20260720-022159-fbba560e27;urp 1>"C:\Users\cntow\AppData\Local\Temp\LibreOfficeMaterialQA\20260720-022159-fbba560e27-vs2026-msi-raster-restart-suppression\soffice.stdout.log" 2>"C:\Users\cntow\AppData\Local\Temp\LibreOfficeMaterialQA\20260720-022159-fbba560e27-vs2026-msi-raster-restart-suppression\soffice.stderr.log"
exit /b %ERRORLEVEL%
