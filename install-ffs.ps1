# FreedomFromSNS — one-command installer (Windows, native — no WSL, no Docker).
#
#   1) One line — paste it into either Command Prompt (cmd) OR PowerShell; it
#      installs to your home (C:\Users\<you>\ffs), or to the folder you run it from
#      if that's a dedicated folder (e.g. cd D:\ffs first):
#      powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/definekorea/freedomfromsns/master/install-ffs.ps1 | iex"
#   2) Or SAVE this file into the folder you want (e.g. D:\ffs), put your Facebook
#      export there too, and run it: powershell -ExecutionPolicy ByPass -File .\install-ffs.ps1
#
# A full log is written to %TEMP%\freedomfromsns-install.log; the window stays open on error.
$ErrorActionPreference = 'Stop'
$Repo = if ($env:FFS_REPO) { $env:FFS_REPO } else { 'definekorea/freedomfromsns' }
$LogFile = Join-Path $env:TEMP 'freedomfromsns-install.log'
try { Stop-Transcript | Out-Null } catch {}
try { Start-Transcript -Path $LogFile -Force | Out-Null } catch {}

$ok = $false
try {
  # Language FIRST — before anything else (only when there's a console to ask in).
  # Passed to `ffs setup` via FFS_LANG so it isn't asked again.
  if (-not $env:FFS_LANG -and $Host.Name -eq 'ConsoleHost') {
    $l = Read-Host "Language / 언어 — [1] English  [2] 한국어 (default 1)"
    $env:FFS_LANG = if ($l -eq '2') { 'ko' } else { 'en' }
  }
  if (-not $env:FFS_LANG) { $env:FFS_LANG = 'en' }
  $ko = $env:FFS_LANG -eq 'ko'

  # Archive home: an explicit FBBACKUP_HOME wins; else the folder this installer runs
  # from (its own dir, or the current dir for the one-liner) IF that's a DEDICATED
  # folder (e.g. D:\ffs) — not a transient one (Downloads/Desktop/Documents/home/temp),
  # which fall through to the default ~/ffs. Nothing hardcoded.
  $base = if ($PSScriptRoot) { $PSScriptRoot } elseif ($MyInvocation.MyCommand.Path) { Split-Path -Parent $MyInvocation.MyCommand.Path } else { (Get-Location).Path }
  $base = $base.TrimEnd('\')
  $IsCheckout = Test-Path (Join-Path $base 'pyproject.toml')
  $transient = @(
    [Environment]::GetFolderPath('UserProfile'), [Environment]::GetFolderPath('Desktop'),
    [Environment]::GetFolderPath('MyDocuments'), (Join-Path $env:USERPROFILE 'Downloads'),
    (Join-Path $env:USERPROFILE 'OneDrive\Desktop'), (Join-Path $env:USERPROFILE 'OneDrive\Documents'),
    (Join-Path $env:USERPROFILE 'OneDrive\Downloads'), $env:TEMP, $env:windir, (Join-Path $env:windir 'System32')
  ) | Where-Object { $_ } | ForEach-Object { $_.TrimEnd('\') }
  if ($base) { $env:FFS_LOOK = $base }   # let the wizard also search in/near here
  if (-not $env:FBBACKUP_HOME -and -not $IsCheckout -and ($transient -notcontains $base)) {
    $env:FBBACKUP_HOME = $base
  }
  if ($env:FBBACKUP_HOME) { Write-Host "Archive folder: $env:FBBACKUP_HOME" }

  # Source: explicit override > local checkout > the HIGHEST-version GitHub Release
  # wheel (we sort by semver — GitHub's /releases/latest can lag/mis-rank).
  if ($env:FFS_SOURCE) {
    $Source = $env:FFS_SOURCE
  } elseif ($IsCheckout) {
    $Source = $base
  } else {
    Write-Host "Finding FreedomFromSNS releases…"
    # Cache-bust: a unique query param + no-cache headers so a proxy/CDN can't serve
    # a stale release list (which would install an OLD version).
    $bust = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
    $rels = irm "https://api.github.com/repos/$Repo/releases?per_page=100&_=$bust" `
                -Headers @{ 'Cache-Control' = 'no-cache'; 'Pragma' = 'no-cache'; 'User-Agent' = 'ffs-installer' }
    $sorted = @($rels | Where-Object { $_.assets } |
                Sort-Object { try { [version]($_.tag_name -replace '^v', '') } catch { [version]'0.0' } } -Descending)
    if (-not $sorted) { throw "No release wheel found for $Repo — has a release been published?" }
    $rel = $sorted[0]
    # Optional version picker: set FFS_PICK=1 (install-ffs.bat does) to choose a
    # version interactively; default (Enter) is the latest. Only when interactive.
    if ($env:FFS_PICK -and $sorted.Count -gt 1 -and $Host.Name -eq 'ConsoleHost') {
      Write-Host ("`n" + $(if ($ko) { "설치 가능한 버전 (최신순):" } else { "Available versions (newest first):" }))
      $max = [Math]::Min(10, $sorted.Count)
      $tagLatest = if ($ko) { "  (최신)" } else { "  (latest)" }
      for ($i = 0; $i -lt $max; $i++) {
        Write-Host ("  [{0}] {1}{2}" -f ($i + 1), $sorted[$i].tag_name, $(if ($i -eq 0) { $tagLatest } else { "" }))
      }
      $pick = Read-Host $(if ($ko) { "설치할 번호를 고르세요 (엔터 = 최신)" } else { "Pick a number to install (Enter = latest)" })
      if ($pick -match '^\d+$' -and [int]$pick -ge 1 -and [int]$pick -le $max) { $rel = $sorted[[int]$pick - 1] }
    }
    $Source = ($rel.assets | Where-Object { $_.name -like '*.whl' } | Select-Object -First 1).browser_download_url
    if (-not $Source) { throw "No release wheel found for $($rel.tag_name)." }
    Write-Host "  installing: $($rel.tag_name)"
  }
  Write-Host "  source: $Source`n"

  # 1. uv — install if missing; make uv + the tool's `ffs` usable here and in children.
  if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Installing uv (Python manager)…"
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  }
  $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
  Write-Host "uv: $(uv --version)"

  # 2. Install the app, then make sure its `ffs` command is on PATH.
  Write-Host "Installing FreedomFromSNS…"
  uv tool install --force $Source
  try { $tb = (uv tool dir --bin 2>$null | Select-Object -First 1); if ($tb) { $env:Path = "$tb;$env:Path" } } catch {}

  # 3. Run setup HERE — one window, no second terminal. The language is already
  #    chosen above (FFS_LANG), so setup goes straight to finding data → build →
  #    (optional) AI → open browser. It serves at the end (Ctrl-C to stop).
  Write-Host "`nStarting setup…`n"
  if (Get-Command ffs -ErrorAction SilentlyContinue) {
    ffs setup
  } else {
    uv tool run --from $Source ffs setup
  }
  $ok = $true   # reached after setup's server is stopped (Ctrl-C) — normal exit
}
catch {
  Write-Host ""
  Write-Host "==========================================================" -ForegroundColor Red
  Write-Host ("  Install did NOT finish: " + $_.Exception.Message) -ForegroundColor Red
  Write-Host "==========================================================" -ForegroundColor Red
  Write-Host $_.ScriptStackTrace -ForegroundColor DarkGray
}
finally {
  try { Stop-Transcript | Out-Null } catch {}
  Write-Host ""
  Write-Host "Full log saved to: $LogFile"
  if (-not $ok) {
    Write-Host ""
    Write-Host "It didn't finish. Read the message above; please send the log file" -ForegroundColor Yellow
    Write-Host "so we can fix it. This window stays open until you press Enter." -ForegroundColor Yellow
    # Pause so nothing vanishes — fall back to a wait if there's no interactive console.
    try { Read-Host "Press Enter to close" | Out-Null } catch { Start-Sleep -Seconds 60 }
  }
}
