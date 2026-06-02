@echo off
title FreedomFromSNS - install / update
echo.
echo  ============================================================
echo    FreedomFromSNS  -  installer / updater   (Windows)
echo  ============================================================
echo.
echo  This installs EVERYTHING for you - it gets uv (a tiny tool,
echo  no admin needed), then the right Python, then the app.
echo  You do NOT need uv, Python, or pip installed beforehand.
echo.
echo  Double-click this file again any time to UPDATE to the
echo  newest version. Your archive data is never touched.
echo.
echo  Working... (a setup window will open shortly)
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/definekorea/freedomfromsns/master/install-ffs.ps1 | iex"
echo.
echo  ------------------------------------------------------------
echo  Setup opens in its own window - follow the prompts there.
echo  If something went wrong, the log is at:
echo     %TEMP%\freedomfromsns-install.log
echo  ------------------------------------------------------------
echo.
pause
