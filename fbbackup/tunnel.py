"""ffs tunnel — a permanent, stable public address via a Cloudflare *named* tunnel.

Unlike the quick tunnel (`ffs share` / the 🌐 Publish button), a named tunnel
survives restarts and lives on your own domain (`archive.yourname.com`). It needs
a free Cloudflare account and a domain whose DNS is on Cloudflare — the one-time
browser **login** and that account/domain **registration** can't be scripted, so
the wizard does the scriptable parts (create tunnel → route DNS → write config →
run) and guides the rest.

It writes a **dedicated** config at ``~/ffs/cloudflared.yml`` and runs cloudflared
with ``--config`` that file, so it never reads or clobbers an existing
``~/.cloudflared/config.yml`` (e.g. someone already running other named tunnels).
"""
from __future__ import annotations

import json
import os
import platform
import stat
import subprocess
import tarfile
import urllib.request
from pathlib import Path
from shutil import which


def _cf_cache_dir() -> Path:
    """Stable per-user dir for an auto-downloaded cloudflared (not on PATH)."""
    base = os.environ.get("LOCALAPPDATA") if os.name == "nt" else None
    root = Path(base) if base else (Path.home() / ".cache")
    d = root / "ffs" / "bin"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cf_local() -> Path:
    return _cf_cache_dir() / ("cloudflared.exe" if os.name == "nt" else "cloudflared")


def cloudflared() -> str | None:
    """A usable cloudflared: system PATH first, else our auto-downloaded copy."""
    p = which("cloudflared")
    if p:
        return p
    local = _cf_local()
    return str(local) if local.exists() else None


def _cf_asset() -> str | None:
    """The official release asset name for this OS/arch (cloudflare/cloudflared)."""
    m = platform.machine().lower()
    arch = ("amd64" if m in ("x86_64", "amd64") else
            "arm64" if m in ("arm64", "aarch64") else
            "386" if m in ("i386", "i686", "x86") else None)
    if os.name == "nt":
        return f"cloudflared-windows-{arch or 'amd64'}.exe"
    if platform.system().lower() == "darwin":
        return f"cloudflared-darwin-{arch or 'amd64'}.tgz"   # macOS ships a .tgz
    return f"cloudflared-linux-{arch or 'amd64'}"


def ensure_cloudflared() -> str | None:
    """Return a cloudflared path, downloading the official binary on demand if it
    isn't on PATH or already cached. ~35 MB, one time. Returns None on failure."""
    p = cloudflared()
    if p:
        return p
    asset = _cf_asset()
    if not asset:
        return None
    url = f"https://github.com/cloudflare/cloudflared/releases/latest/download/{asset}"
    dest = _cf_local()
    try:
        if asset.endswith(".tgz"):
            tmp = dest.with_name(dest.name + ".tgz")
            urllib.request.urlretrieve(url, tmp)
            with tarfile.open(tmp) as tf:
                member = next(m for m in tf.getmembers() if m.name.rstrip("/").endswith("cloudflared"))
                with tf.extractfile(member) as src, open(dest, "wb") as out:
                    out.write(src.read())
            tmp.unlink(missing_ok=True)
        else:
            urllib.request.urlretrieve(url, dest)
        if os.name != "nt":
            dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return str(dest) if dest.exists() else None
    except Exception:  # noqa: BLE001
        return None


def cf_dir() -> Path:
    return Path.home() / ".cloudflared"


def is_logged_in() -> bool:
    """A successful ``cloudflared tunnel login`` writes cert.pem here."""
    return (cf_dir() / "cert.pem").is_file()


def list_tunnels() -> list[dict]:
    exe = cloudflared()
    if not exe:
        return []
    try:
        out = subprocess.run([exe, "tunnel", "list", "--output", "json"],
                             capture_output=True, text=True, timeout=25)
        return json.loads(out.stdout or "[]") or []
    except Exception:  # noqa: BLE001
        return []


def tunnel_by_name(name: str) -> dict | None:
    for t in list_tunnels():
        if t.get("name") == name:
            return t
    return None


def tunnel_id(t: dict) -> str:
    return str(t.get("id") or t.get("ID") or "")


def create_tunnel(name: str) -> dict | None:
    """Create a named tunnel (idempotent at the call site — check existence first).
    Returns the tunnel record (with its id), or None on failure."""
    exe = cloudflared()
    if not exe:
        return None
    subprocess.run([exe, "tunnel", "create", name], timeout=60)
    return tunnel_by_name(name)


def credentials_file(tid: str) -> Path:
    return cf_dir() / f"{tid}.json"


def route_dns(name: str, hostname: str) -> bool:
    exe = cloudflared()
    if not exe:
        return False
    return subprocess.run([exe, "tunnel", "route", "dns", name, hostname], timeout=40).returncode == 0


def write_config(home: Path, tid: str, hostname: str, port: int) -> Path:
    """Write a dedicated ``~/ffs/cloudflared.yml`` (never touches the global config)."""
    cfg = home / "cloudflared.yml"
    cfg.write_text(
        f"tunnel: {tid}\n"
        f"credentials-file: {credentials_file(tid)}\n\n"
        f"ingress:\n"
        f"  - hostname: {hostname}\n"
        f"    service: http://localhost:{port}\n"
        f"  - service: http_status:404\n",
        encoding="utf-8")
    return cfg


def run_command(home: Path) -> list[str]:
    """Run the tunnel from our dedicated config (the config names the tunnel, so the
    same saved address is reused — no id/name needed here)."""
    return [cloudflared() or "cloudflared", "tunnel", "--config",
            str(home / "cloudflared.yml"), "run"]


def read_config(home: Path) -> dict:
    """Parse a previously-saved ~/ffs/cloudflared.yml → {tunnel, hostname}. Survives
    uninstall (it's in the data folder), so the public address is reused."""
    f = home / "cloudflared.yml"
    out: dict = {}
    if f.is_file():
        for line in f.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s.startswith("tunnel:"):
                out["tunnel"] = s.split(":", 1)[1].strip()
            elif "hostname:" in s and "hostname" not in out:
                out["hostname"] = s.split("hostname:", 1)[1].strip()
    return out


def tunnel_exists(tid: str) -> bool:
    return bool(tid) and any(tunnel_id(t) == tid for t in list_tunnels())
