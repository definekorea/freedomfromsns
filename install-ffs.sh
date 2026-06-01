#!/usr/bin/env sh
# FreedomFromSNS — one-command installer (macOS / Linux).
#
# Installs uv (one static binary that manages a pinned Python — so you never
# install Python, a venv, or ffmpeg by hand), then FreedomFromSNS, then launches
# the setup wizard: it finds your Facebook download, builds your archive, and
# opens it in the browser. No API key needed for browsing — that's optional.
#
#   curl -LsSf https://…/install-ffs.sh | sh        # end users (from the published package)
#   ./install-ffs.sh                                # from a source checkout (installs this copy)
#   FFS_SOURCE=/path/or/git+url ./install-ffs.sh    # explicit source
#   ./install-ffs.sh --yes --no-serve               # extra args are forwarded to `ffs setup`
set -eu

# Source: explicit override > local checkout (this script sits next to pyproject)
# > the latest GitHub Release wheel (no PyPI, no git, no clone — uv installs the
# wheel straight from its HTTPS URL).
REPO="${FFS_REPO:-definekorea/freedomfromsns}"
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd 2>/dev/null) || SCRIPT_DIR=""
# Let the wizard search in/near the installer; and if this file lives in a DEDICATED
# folder (not a transient one like Downloads/Desktop/Documents/home/tmp), make that
# folder the archive home. Transient ones fall through to the default (~/ffs).
if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/install-ffs.sh" ]; then
  export FFS_LOOK="$SCRIPT_DIR"
  case "$SCRIPT_DIR" in
    "$HOME"|"$HOME/Downloads"|"$HOME/Desktop"|"$HOME/Documents"|/tmp|/tmp/*) : ;;
    *) [ -z "${FBBACKUP_HOME:-}" ] && [ ! -f "$SCRIPT_DIR/pyproject.toml" ] && export FBBACKUP_HOME="$SCRIPT_DIR" ;;
  esac
fi
if [ -n "${FFS_SOURCE:-}" ]; then
  SOURCE="$FFS_SOURCE"
elif [ -f "$SCRIPT_DIR/pyproject.toml" ]; then
  SOURCE="$SCRIPT_DIR"
else
  echo "Finding the latest FreedomFromSNS release…"
  SOURCE=$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" \
           | grep -o 'https://[^"]*\.whl' | head -1)
  [ -n "$SOURCE" ] || { echo "No release wheel found for $REPO — has a release been published?"; exit 1; }
fi

echo "FreedomFromSNS installer"
echo "  source: $SOURCE"
echo

# 1. uv — install if missing, and make it usable in THIS shell.
if ! command -v uv >/dev/null 2>&1; then
  echo "Installing uv (Python manager)…"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  [ -f "$HOME/.local/bin/env" ] && . "$HOME/.local/bin/env"
  export PATH="$HOME/.local/bin:$PATH"
fi
echo "uv: $(uv --version)"

# 2. Install the app. uv brings its own pinned Python; the default install is
#    pure-Python wheels (Tier 0) — no compiler, no ffmpeg, no model downloads.
echo "Installing FreedomFromSNS…"
uv tool install --force "$SOURCE"

# 3. Run the wizard (pick language → find data → build → open). Extra args pass through.
echo
echo "Launching setup…"
uv tool run --from "$SOURCE" ffs setup "$@"

echo
echo "Done. From now on just run:  ffs serve      (re-run  ffs setup  to reconfigure)"
echo "If 'ffs' isn't found, restart your terminal (uv added it to your PATH)."
