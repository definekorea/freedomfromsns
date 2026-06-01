"""System-tray control center (pystray + Pillow).

One place to run FreedomFromSNS: a tray icon whose **colour shows server status**
(green = running · grey = stopped · blue = published) and a click menu —
Open · Start/Stop server · Publish on the web · Start at login · Quit.

The server runs as a detached background process; the icon talks to it over the
loopback API (/, /api/publish/*, /api/quit), so it controls whatever instance is
up (even one started at login). Headless/import failures fall back to a plain
serve (see cli.cmd_tray). Imports here are lazy so the module loads anywhere.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

_COLORS = {"running": (60, 170, 90), "stopped": (150, 150, 150), "published": (60, 120, 210)}


def _icon(color: tuple) -> "object":
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse((8, 8, 56, 56), fill=color)
    return img


def _get(url: str, timeout: float = 1.5):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.status, r.read()


def _post(url: str, timeout: float = 20):
    urllib.request.urlopen(urllib.request.Request(url, method="POST"), timeout=timeout).read()


class Tray:
    def __init__(self, host: str, port: int, home: Path):
        self.url = f"http://{'127.0.0.1' if host in ('0.0.0.0', '', '::', '::1') else host}:{port}"
        self.home = home
        self.proc: subprocess.Popen | None = None
        self.icon = None

    # ── server state over the loopback API ────────────────────────────────────
    def up(self) -> bool:
        try:
            return _get(self.url + "/")[0] == 200
        except Exception:  # noqa: BLE001
            return False

    def published(self) -> bool:
        try:
            return bool(json.loads(_get(self.url + "/api/publish/status")[1]).get("running"))
        except Exception:  # noqa: BLE001
            return False

    def state(self) -> str:
        if not self.up():
            return "stopped"
        return "published" if self.published() else "running"

    def start_server(self) -> None:
        if self.up():
            return
        env = dict(os.environ, FBBACKUP_HOME=str(self.home))
        kw: dict = {"creationflags": 0x00000008} if os.name == "nt" else {"start_new_session": True}
        self.proc = subprocess.Popen([sys.executable, "-m", "fbbackup.cli", "serve"],
                                     env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kw)
        for _ in range(30):                      # wait up to ~6s for it to answer
            if self.up():
                break
            time.sleep(0.2)

    def stop_server(self) -> None:
        if self.up():
            try:
                _post(self.url + "/api/quit", timeout=3)   # works for any local instance
            except Exception:  # noqa: BLE001
                pass
        self.proc = None

    # ── run the tray ──────────────────────────────────────────────────────────
    def run(self) -> int:
        import pystray
        from . import setup as wiz

        self.start_server()
        webbrowser.open(self.url)                # bring up the page on launch

        def _open(icon, item):
            webbrowser.open(self.url)

        def _toggle_server(icon, item):
            (self.stop_server if self.up() else self.start_server)()
            self._refresh()

        def _toggle_publish(icon, item):
            try:
                _post(self.url + ("/api/publish/stop" if self.published() else "/api/publish/start"))
            except Exception:  # noqa: BLE001
                pass
            self._refresh()

        def _toggle_autostart(icon, item):
            (wiz.disable_autostart() if wiz.autostart_status() else wiz.enable_autostart(self.home))
            self._refresh()

        def _quit(icon, item):
            self.stop_server()
            icon.stop()

        menu = pystray.Menu(
            pystray.MenuItem("Open FreedomFromSNS", _open, default=True),
            pystray.MenuItem(lambda i: "Stop server" if self.up() else "Start server", _toggle_server),
            pystray.MenuItem("Publish on the web", _toggle_publish, checked=lambda i: self.published()),
            pystray.MenuItem("Start at login", _toggle_autostart, checked=lambda i: wiz.autostart_status()),
            pystray.MenuItem("Quit", _quit),
        )
        self.icon = pystray.Icon("freedomfromsns", _icon(_COLORS["running"]), "FreedomFromSNS", menu)
        threading.Thread(target=self._poll, daemon=True).start()
        self.icon.run()                          # blocks until Quit
        return 0

    def _refresh(self) -> None:
        try:
            self.icon.icon = _icon(_COLORS[self.state()])
            self.icon.update_menu()
        except Exception:  # noqa: BLE001
            pass

    def _poll(self) -> None:
        while True:
            time.sleep(3)
            if not self.icon:
                break
            self._refresh()


def run(host: str, port: int, home: Path) -> int:
    return Tray(host, port, home).run()
