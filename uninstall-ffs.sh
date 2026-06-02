#!/usr/bin/env sh
# FreedomFromSNS — uninstaller (macOS / Linux / WSL). Removes the program, launchers,
# auto-start, and caches — but KEEPS your archive folder (data / index / config).
#
#   curl -fsSL https://raw.githubusercontent.com/definekorea/freedomfromsns/master/uninstall-ffs.sh | sh
ARCHIVE_DIR="${FBBACKUP_HOME:-$HOME/ffs}"
echo "Removing FreedomFromSNS (your data at $ARCHIVE_DIR will be kept)…"

# desktop launchers (Desktop and the archive folder)
for d in "$HOME/Desktop" "$ARCHIVE_DIR"; do
  rm -f "$d/FreedomFromSNS.command" "$d/FreedomFromSNS.sh" \
        "$d/FreedomFromSNS (Add data).command" "$d/FreedomFromSNS (Add data).sh" 2>/dev/null || true
done

# auto-start (Linux XDG + macOS LaunchAgent)
rm -f "$HOME/.config/autostart/freedomfromsns.desktop" 2>/dev/null || true
if [ -f "$HOME/Library/LaunchAgents/com.freedomfromsns.plist" ]; then
  launchctl unload "$HOME/Library/LaunchAgents/com.freedomfromsns.plist" 2>/dev/null || true
  rm -f "$HOME/Library/LaunchAgents/com.freedomfromsns.plist" 2>/dev/null || true
fi

# NB: we deliberately KEEP all Cloudflare bits so a reinstall reuses the same public
# address — the config ($ARCHIVE_DIR/cloudflared.yml), the login/tunnel creds
# (~/.cloudflared), and the downloaded cloudflared binary (~/.cache/ffs).

# the program itself (uv-managed Python tool)
uv tool uninstall freedomfromsns || true

echo
echo "Done. Kept: your archive at $ARCHIVE_DIR + your Cloudflare address/login (reused on reinstall)."

# Big downloaded-model files are KEPT by default (so a reinstall doesn't re-download
# gigabytes). Tell the user where they are, to free the space if they want.
shown=""
for d in "$HOME/.cache/ffs/localchat" "${TMPDIR:-/tmp}/fastembed_cache" "$HOME/.cache/fastembed"; do
  if [ -d "$d" ]; then
    [ -z "$shown" ] && echo && echo "Kept downloaded AI model files (so a reinstall needs no re-download):" && shown=1
    echo "   $d  ($(du -sh "$d" 2>/dev/null | cut -f1))"
  fi
done
[ -n "$shown" ] && echo "To free that space, delete those folders (they re-download if needed)."
echo
echo "If you also want the data gone, delete $ARCHIVE_DIR yourself."
