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

# caches (auto-downloaded cloudflared)
rm -rf "$HOME/.cache/ffs" 2>/dev/null || true

# the program itself (uv-managed Python tool)
uv tool uninstall freedomfromsns || true

echo
echo "Done. Your archive is preserved at: $ARCHIVE_DIR"
echo "If you also want the data gone, delete that folder yourself."
