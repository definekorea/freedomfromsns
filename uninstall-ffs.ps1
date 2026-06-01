# FreedomFromSNS — uninstaller (Windows). Removes the program, desktop launchers,
# auto-start, and caches — but KEEPS your archive folder (data / index / config).
#
#   powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/definekorea/freedomfromsns/master/uninstall-ffs.ps1 | iex"
$ErrorActionPreference = 'SilentlyContinue'
$ArchiveDir = if ($env:FBBACKUP_HOME) { $env:FBBACKUP_HOME } else { Join-Path $env:USERPROFILE 'ffs' }
Write-Host "Removing FreedomFromSNS (your data at $ArchiveDir will be kept)…"

# desktop launchers (Desktop, OneDrive Desktop, and the archive folder)
$dirs  = @("$env:USERPROFILE\Desktop", "$env:USERPROFILE\OneDrive\Desktop", $ArchiveDir)
$names = @('FreedomFromSNS.cmd', 'FreedomFromSNS (Add data).cmd')
foreach ($d in $dirs) { foreach ($n in $names) { Remove-Item (Join-Path $d $n) -Force -ErrorAction SilentlyContinue } }

# auto-start entry + background server launcher
Remove-Item "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\FreedomFromSNS.vbs" -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $ArchiveDir 'ffs-server.cmd') -Force -ErrorAction SilentlyContinue

# NB: we deliberately KEEP all Cloudflare bits so a reinstall reuses the same public
# address — the config ($ArchiveDir\cloudflared.yml), the login/tunnel creds
# (~\.cloudflared), and the downloaded cloudflared binary ($env:LOCALAPPDATA\ffs).

# the program itself (uv-managed Python tool)
uv tool uninstall freedomfromsns

Write-Host ""
Write-Host "Done. Kept: your archive at $ArchiveDir + your Cloudflare address/login (reused on reinstall)."
Write-Host "If you also want the data gone, delete that folder yourself."
