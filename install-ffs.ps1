# FreedomFromSNS — one-command installer (Windows, native — no WSL, no Docker).
#
# Installs uv (one binary that manages a pinned Python — so you never install
# Python, a venv, or ffmpeg by hand), then FreedomFromSNS, then launches the
# setup wizard: it finds your Facebook download, builds your archive, and opens
# it in your browser. Browsing needs no API key — that's optional.
#
#   # end users (from the published package):
#   powershell -ExecutionPolicy ByPass -c "irm https://…/install-ffs.ps1 | iex"
#   # from a source checkout (installs this copy):
#   powershell -ExecutionPolicy ByPass -File .\install-ffs.ps1
#   # explicit source / extra args forwarded to `ffs setup`:
#   $env:FFS_SOURCE='C:\path\or\git+url'; .\install-ffs.ps1 --yes --no-serve
$ErrorActionPreference = 'Stop'

# Source: explicit override > local checkout (script sits next to pyproject) > the
# latest GitHub Release wheel (no PyPI, no git, no clone — uv installs the wheel
# straight from its HTTPS URL; irm parses the release JSON natively).
$Repo = if ($env:FFS_REPO) { $env:FFS_REPO } else { 'definekorea/freedomfromsns' }
$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
if ($env:FFS_SOURCE) {
  $Source = $env:FFS_SOURCE
} elseif ($ScriptDir -and (Test-Path (Join-Path $ScriptDir 'pyproject.toml'))) {
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

# 2. Install the app. uv brings its own pinned Python; the default install is
#    pure-Python wheels (Tier 0) — no compiler, no ffmpeg, no model downloads.
Write-Host "Installing FreedomFromSNS…"
uv tool install --force $Source

# 3. Run the wizard (pick language → find data → build → open). Extra args pass through.
Write-Host "`nLaunching setup…"
uv tool run --from $Source ffs setup @args

Write-Host "`nDone. From now on just run:  ffs serve      (re-run  ffs setup  to reconfigure)"
Write-Host "If 'ffs' isn't found, open a new terminal (uv added it to your PATH)."
