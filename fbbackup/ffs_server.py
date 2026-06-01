"""FreedomFromSNS — the standalone local server.

Assembles one FastAPI app: the SpacesBackend (browse / semantic search / media
serve / unfurl over the md rows, mounted at `/api/fb/*`), the SPA-facing API
(`/api/index`, `/api/search`, `/api/chat` — Gemini-direct), and the polished
single-page viewer at `/`. One process, one Gemini key, one port (8282).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from . import ffs_api
from .spaces_backend import SpacesBackend

_PKG = Path(__file__).resolve().parent
_VIEWER = _PKG.parent / "viewer"


def create_app(spaces_root: Path, export_root: Path,
               chat_model: str = "gemini-flash-latest") -> FastAPI:
    spaces_root = Path(spaces_root).expanduser()
    if not spaces_root.is_dir():
        raise SystemExit(f"No rows at {spaces_root} — run `ffs build` first.")
    app = FastAPI(title="FreedomFromSNS")
    # media_roots: the read-only export (where image abs_paths live) + the vault
    # (added inside SpacesBackend) so `/api/fb/files` can serve archive photos.
    b = SpacesBackend(spaces_root, media_roots=[Path(export_root).expanduser()], prefix="/api/fb")
    b.register(app, prefix="/api/fb")
    ffs_api.DEFAULT_MODEL = chat_model
    ffs_api.register(app, b)

    @app.on_event("startup")
    def _warm() -> None:  # build the in-memory index off-thread so the first
        import threading   # request isn't a multi-second cold scan of 10k+ files
        threading.Thread(target=lambda: b._ensure_index("default"), daemon=True).start()

    @app.get("/", response_class=HTMLResponse)
    def home():
        html = (_VIEWER / "index.html").read_text(encoding="utf-8")
        # auto cache-bust the SPA assets by file mtime, so an edit is always
        # picked up without a manual hard-reload (and stale CSS can't mislead).
        for name in ("fb-app.css", "fb-app.js"):
            try:
                v = int((_VIEWER / name).stat().st_mtime)
            except OSError:
                v = 1
            html = html.replace(f"/static/{name}", f"/static/{name}?v={v}")
        # Logo emblems are auto-discovered from viewer/logo-candidates/ (sorted by
        # name → controllable order). Drop/replace a png there and it joins the
        # brand's click-to-rotate set; mtime-busting picks up replacements.
        logos = []
        logo_dir = _VIEWER / "logo-candidates"
        if logo_dir.is_dir():
            for f in sorted(logo_dir.iterdir()):
                if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".svg"):
                    logos.append(f"/static/logo-candidates/{f.name}?v={int(f.stat().st_mtime)}")
        html = html.replace("__FFS_LOGOS__", json.dumps(logos))
        # Themes are auto-discovered from viewer/themes/*.json (sorted by name;
        # 00-default is first). Each is {name, tokens}; the frontend applies a
        # theme's tokens as :root custom properties. Drop a json there → new theme.
        themes = []
        theme_dir = _VIEWER / "themes"
        if theme_dir.is_dir():
            for f in sorted(theme_dir.glob("*.json")):
                try:
                    t = json.loads(f.read_text("utf-8"))
                except Exception:
                    continue
                if isinstance(t, dict) and isinstance(t.get("tokens"), dict):
                    themes.append({"name": t.get("name") or f.stem, "tokens": t["tokens"]})
        html = html.replace("__FFS_THEMES__", json.dumps(themes))
        # Chat models = the active provider's two lanes (settings.json), so the
        # selector + default follow whatever provider the user connected.
        from . import providers
        chat = providers.load_settings()["chat"]
        html = html.replace("__FFS_MODELS__",
                            json.dumps([chat["fast_model"], chat["precise_model"]]))
        html = html.replace("__FFS_DEFAULT_MODEL__", json.dumps(chat["fast_model"]))
        html = html.replace("__FFS_CHAT_PROVIDER__", json.dumps(chat["provider"]))
        return html

    app.mount("/static", StaticFiles(directory=_VIEWER), name="static")
    return app


def _reload_app() -> FastAPI:
    """App factory for `--reload` (uvicorn must import the app by string).
    Reads the paths the parent stashed in the env before handing off."""
    return create_app(os.environ["FFS_SPACES"], os.environ["FFS_EXPORT"],
                      os.environ.get("FFS_CHAT_MODEL", "gemini-flash-latest"))


def serve(spaces_root: Path, export_root: Path, host: str = "127.0.0.1",
          port: int = 8282, chat_model: str = "gemini-flash-latest",
          reload: bool = False) -> None:
    import uvicorn
    if reload:
        # auto-reload on Python edits only (watch the package, not viewer/ — the
        # frontend is static + cache-busted, so it never needs a server restart).
        os.environ["FFS_SPACES"] = str(spaces_root)
        os.environ["FFS_EXPORT"] = str(export_root)
        os.environ["FFS_CHAT_MODEL"] = chat_model
        uvicorn.run("fbbackup.ffs_server:_reload_app", factory=True, host=host,
                    port=port, reload=True, reload_dirs=[str(_PKG)])
    else:
        uvicorn.run(create_app(spaces_root, export_root, chat_model), host=host, port=port)
