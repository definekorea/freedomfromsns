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
import subprocess
from pathlib import Path
from shutil import which


def cloudflared() -> str | None:
    return which("cloudflared")


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


def run_command(home: Path, name: str) -> list[str]:
    """The command that runs the tunnel using our dedicated config."""
    return [cloudflared() or "cloudflared", "tunnel", "--config",
            str(home / "cloudflared.yml"), "run", name]
