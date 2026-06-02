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

# Big downloaded-model files are KEPT by default (so a reinstall doesn't re-download
# gigabytes). Tell the user where they are + total size, so they can free space.
$caches = @(
  (Join-Path $env:LOCALAPPDATA 'ffs\localchat'),   # local chat: llama-server + GGUF models
  (Join-Path $env:TEMP 'fastembed_cache'),         # local search: embedding model
  (Join-Path $env:USERPROFILE '.cache\fastembed')
) | Where-Object { Test-Path $_ }
if ($caches) {
  $total = 0
  $rows = foreach ($d in $caches) {
    $sz = (Get-ChildItem $d -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
    $total += $sz
    [pscustomobject]@{ Path = $d; MB = [Math]::Round($sz / 1MB) }
  }
  Write-Host ""
  Write-Host ("Kept ~{0:N0} MB of downloaded AI model files (so a reinstall needs no re-download):" -f ($total / 1MB)) -ForegroundColor Cyan
  foreach ($r in $rows) { Write-Host ("   {0}  (~{1:N0} MB)" -f $r.Path, $r.MB) }
  Write-Host "To free that space, delete those folders. (Safe — they re-download if needed.)"
}
Write-Host ""
Write-Host "If you also want the data gone, delete $ArchiveDir yourself."
