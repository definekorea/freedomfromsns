@echo off
title FreedomFromSNS - uninstall
echo.
echo  ============================================================
echo    FreedomFromSNS  -  uninstall   (Windows)
echo  ============================================================
echo.
echo  Removes the program and its launchers. Your archive data
echo  and Cloudflare settings are KEPT (a reinstall reuses them).
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/definekorea/freedomfromsns/master/uninstall-ffs.ps1 | iex"
echo.
pause
