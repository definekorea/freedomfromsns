# FreedomFromSNS — one-command installer (Windows, native — no WSL, no Docker).
#
# Two ways to run:
#   1) One line — installs to your home (C:\Users\<you>\ffs):
#      powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/definekorea/freedomfromsns/master/install-ffs.ps1 | iex"
#   2) Your own folder — SAVE this file into the folder you want (e.g. D:\ffs), put
#      your Facebook export in that same folder, then run it there:
#      powershell -ExecutionPolicy ByPass -File .\install-ffs.ps1
#      → that folder becomes your archive home. Nothing hardcoded, no path typing.
#
# A full log is always written to %TEMP%\freedomfromsns-install.log, and the
# window stays open on error so you can read/send it.
$ErrorActionPreference = 'Stop'
$Repo = if ($env:FFS_REPO) { $env:FFS_REPO } else { 'definekorea/freedomfromsns' }
$LogFile = Join-Path $env:TEMP 'freedomfromsns-install.log'
try { Stop-Transcript | Out-Null } catch {}
try { Start-Transcript -Path $LogFile -Force | Out-Null } catch {}

$ok = $false
try {
  # Where state lives + where to look for data. Priority: an explicit FBBACKUP_HOME,
  # else the folder THIS installer file sits in (so "drop it in your folder + run"
  # just works — nothing hardcoded), else the default (~/ffs, the one-liner case).
  $ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } elseif ($MyInvocation.MyCommand.Path) { Split-Path -Parent $MyInvocation.MyCommand.Path } else { $null }
  $IsCheckout = $ScriptDir -and (Test-Path (Join-Path $ScriptDir 'pyproject.toml'))
  # Adopt the installer's OWN folder as the archive home only if it's a DEDICATED
  # folder (e.g. D:\ffs) — not a transient one like Downloads/Desktop/Documents,
  # where people just drop the installer next to their FB zip. Those fall through
  # to the default (~/ffs), and the wizard auto-detects + extracts the FB zip.
  $transient = @(
    [Environment]::GetFolderPath('UserProfile'), [Environment]::GetFolderPath('Desktop'),
    [Environment]::GetFolderPath('MyDocuments'), (Join-Path $env:USERPROFILE 'Downloads'),
    (Join-Path $env:USERPROFILE 'OneDrive\Desktop'), (Join-Path $env:USERPROFILE 'OneDrive\Documents'),
    (Join-Path $env:USERPROFILE 'OneDrive\Downloads'), $env:TEMP, $env:windir, (Join-Path $env:windir 'System32')
  ) | Where-Object { $_ } | ForEach-Object { $_.TrimEnd('\') }
  $sd = if ($ScriptDir) { $ScriptDir.TrimEnd('\') } else { $null }
  if ($sd) { $env:FFS_LOOK = $sd }   # let the wizard also search in/near the installer
  if (-not $env:FBBACKUP_HOME -and $sd -and -not $IsCheckout -and ($transient -notcontains $sd)) {
    $env:FBBACKUP_HOME = $sd
  }
  if ($env:FBBACKUP_HOME) { Write-Host "Archive folder: $env:FBBACKUP_HOME" }

  # Source: explicit override > local checkout > the latest GitHub Release wheel.
  if ($env:FFS_SOURCE) {
    $Source = $env:FFS_SOURCE
  } elseif ($IsCheckout) {
    $Source = $ScriptDir
  } else {
    Write-Host "Finding the latest FreedomFromSNS release…"
    $rel = irm "https://api.github.com/repos/$Repo/releases/latest"
    $Source = ($rel.assets | Where-Object { $_.name -like '*.whl' } | Select-Object -First 1).browser_download_url
    if (-not $Source) { throw "No release wheel found for $Repo — has a release been published?" }
  }
  Write-Host "FreedomFromSNS installer"
  Write-Host "  source: $Source`n"

  # 1. uv — install if missing, and make it usable in THIS session.
  if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Installing uv (Python manager)…"
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
  }
  Write-Host "uv: $(uv --version)"

  # 2. Install the app (pure-Python wheels — no compiler, no ffmpeg, no model downloads).
  Write-Host "Installing FreedomFromSNS…"
  uv tool install --force $Source

  # 3. Run the wizard (language → find data → build → open). Extra args pass through.
  Write-Host "`nLaunching setup…"
  uv tool run --from $Source ffs setup @args
  $ok = $true
}
catch {
  Write-Host ""
  Write-Host ("Install failed: " + $_.Exception.Message) -ForegroundColor Red
  Write-Host $_.ScriptStackTrace
}
finally {
  try { Stop-Transcript | Out-Null } catch {}
  Write-Host ""
  Write-Host "Full log saved to: $LogFile"
  if (-not $ok) {
    Write-Host "Something went wrong — please send that log file." -ForegroundColor Yellow
    if ($Host.Name -eq 'ConsoleHost') { Read-Host "Press Enter to close" | Out-Null }
  }
}
