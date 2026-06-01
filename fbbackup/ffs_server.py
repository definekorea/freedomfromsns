"""FreedomFromSNS — the standalone local server.

Assembles one FastAPI app: the SpacesBackend (browse / semantic search / media
serve / unfurl over the md rows, mounted at `/api/fb/*`), the SPA-facing API
(`/api/index`, `/api/search`, `/api/chat` — Gemini-direct), and the polished
single-page viewer at `/`. One process, one Gemini key, one port (8282).
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from . import ffs_api
from .spaces_backend import SpacesBackend

_PKG = Path(__file__).resolve().parent
_VIEWER = _PKG.parent / "viewer"


def create_app(spaces_root: Path, export_root: Path,
               chat_model: str = "gemini-2.5-flash") -> FastAPI:
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
        return html

    app.mount("/static", StaticFiles(directory=_VIEWER), name="static")
    return app


def serve(spaces_root: Path, export_root: Path, host: str = "127.0.0.1",
          port: int = 8282, chat_model: str = "gemini-2.5-flash") -> None:
    import uvicorn
    uvicorn.run(create_app(spaces_root, export_root, chat_model), host=host, port=port)
