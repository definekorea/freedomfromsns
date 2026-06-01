"""Local, no-key AI chat via PrismML **Ternary Bonsai** (1.58-bit) on llama.cpp.

A Tier-2 chat option that needs no API key and runs on low-powered, GPU-less
devices: download a prebuilt ``llama-server`` (PrismML's llama.cpp fork — it has
the Q2_0 ternary kernels stock llama.cpp lacks) plus the Bonsai-1.7B Q2_0 GGUF,
and run a loopback OpenAI-compatible server. The existing chat path
(``providers.chat_complete`` in OpenAI wire format) talks to it unchanged, so this
module only handles the binary/model download + the server lifecycle.

RAG-only (the agentic tool-loop is Gemini-native). Honest tradeoffs: a 1.7B
ternary model is fast and free but weaker than a frontier API and English-centric
— Korean answers are rough. It's the "runs offline on a weak machine" path, not a
Gemini replacement. Binaries: github.com/PrismML-Eng/llama.cpp; model:
huggingface.co/prism-ml/Ternary-Bonsai-1.7B-gguf.
"""
from __future__ import annotations

import os
import platform
import subprocess
import sys
import tarfile
import time
import urllib.request
import zipfile
from pathlib import Path

PORT = 8284                       # loopback OpenAI server (distinct from serve 8282)
PROVIDER = "bonsai"               # the providers.py chat-provider id pointing here
_REL = "prism-b8846-d104cf1"      # PrismML-Eng/llama.cpp release with the ternary kernels
_BASE = f"https://github.com/PrismML-Eng/llama.cpp/releases/download/{_REL}"
_MODEL_FILE = "Ternary-Bonsai-1.7B-Q2_0.gguf"
_MODEL_URL = f"https://huggingface.co/prism-ml/Ternary-Bonsai-1.7B-gguf/resolve/main/{_MODEL_FILE}"
_MODEL_MIN_BYTES = 200_000_000    # sanity floor: a complete 1.7B Q2_0 is ~0.6 GB


def _asset() -> tuple[str, str]:
    """(release-asset filename, archive kind) of the CPU server build for this OS/arch."""
    arm = platform.machine().lower() in ("arm64", "aarch64")
    if os.name == "nt":   # Windows uses upstream-style names (no release tag in the asset)
        return (f"llama-bin-win-cpu-{'arm64' if arm else 'x64'}.zip", "zip")
    if sys.platform == "darwin":   # _REL already begins with "prism-" → "llama-{_REL}-…"
        return (f"llama-{_REL}-bin-macos-{'arm64' if arm else 'x64'}.tar.gz", "tar")
    return (f"llama-{_REL}-bin-ubuntu-{'arm64' if arm else 'x64'}.tar.gz", "tar")


def cache_dir() -> Path:
    base = (Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ffs" / "bonsai"
            if os.name == "nt" else Path.home() / ".cache" / "ffs" / "bonsai")
    base.mkdir(parents=True, exist_ok=True)
    return base


def _server_exe(d: Path) -> Path | None:
    name = "llama-server.exe" if os.name == "nt" else "llama-server"
    hits = sorted(d.rglob(name))
    return hits[0] if hits else None


def _download(url: str, dest: Path, label: str) -> None:
    """Stream a download to dest with a coarse progress line (best-effort). Prints
    only when the whole-percent changes, so it's one updating line, not a flood."""
    last = [-1]
    def hook(blocks, bs, total):
        if total > 0:
            pct = min(100, int(blocks * bs * 100 / total))
            if pct != last[0]:
                last[0] = pct
                print(f"\r  {label}: {pct}%  ({total // (1024 * 1024)} MB)", end="", flush=True)
    urllib.request.urlretrieve(url, dest, reporthook=hook)
    print(flush=True)


def ensure_binary() -> Path | None:
    """Download + extract the prebuilt llama-server once; cached thereafter."""
    d = cache_dir() / "bin"
    exe = _server_exe(d) if d.is_dir() else None
    if exe:
        return exe
    d.mkdir(parents=True, exist_ok=True)
    asset, kind = _asset()
    arc = d / asset
    _download(f"{_BASE}/{asset}", arc, "server")
    if kind == "zip":
        with zipfile.ZipFile(arc) as z:
            z.extractall(d)
    else:
        with tarfile.open(arc) as t:
            t.extractall(d)
    arc.unlink(missing_ok=True)
    exe = _server_exe(d)
    if exe and os.name != "nt":
        exe.chmod(0o755)
    return exe


def ensure_model() -> Path:
    """Download the Bonsai Q2_0 GGUF once; cached thereafter."""
    m = cache_dir() / _MODEL_FILE
    if not m.is_file() or m.stat().st_size < _MODEL_MIN_BYTES:
        _download(_MODEL_URL, m, "model")
    return m


def is_up(port: int = PORT) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def start(port: int = PORT, wait: int = 90) -> bool:
    """Ensure the binary + model are present and a server is listening. Returns True
    once /health responds (model load can take a while on a weak CPU)."""
    if is_up(port):
        return True
    exe = ensure_binary()
    if not exe:
        return False
    model = ensure_model()
    threads = max(1, (os.cpu_count() or 2) - 1)
    args = [str(exe), "-m", str(model), "--host", "127.0.0.1", "--port", str(port),
            "-c", "4096", "-t", str(threads)]
    log = open(cache_dir() / "server.log", "ab")
    kw: dict = {}
    if os.name == "nt":
        kw["creationflags"] = 0x00000008 | 0x00000200   # DETACHED_PROCESS | NEW_PROCESS_GROUP
    else:
        kw["start_new_session"] = True
    subprocess.Popen(args, stdout=log, stderr=log, stdin=subprocess.DEVNULL, **kw)
    for _ in range(wait):
        if is_up(port):
            return True
        time.sleep(1)
    return is_up(port)
