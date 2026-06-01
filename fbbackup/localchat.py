"""Local, no-key AI chat — a bundled ``llama-server`` running a small GGUF model.

A Tier-2 chat option that needs no API key and runs on modest, GPU-less hardware:
we download a prebuilt ``llama-server`` (PrismML's llama.cpp fork — it carries the
Q2_0 ternary kernels stock llama.cpp lacks, and runs ordinary GGUFs too) plus a
small instruct GGUF, and run a loopback OpenAI-compatible server. The existing chat
path (``providers.chat_complete`` in OpenAI wire format) talks to it unchanged.

Three curated models (measured on this archive's Korean RAG prompts, June 2026):
  exaone — LG **EXAONE 3.5 2.4B** (Korean-native, bilingual): best Korean answers;
           the default and the right pick for a Korean archive.
  qwen3  — **Qwen3 1.7B** (multilingual): correct + lighter; thinking disabled at
           launch (--reasoning off) so it replies directly.
  bonsai — PrismML **Ternary Bonsai 1.7B** (1.58-bit): ultralight/offline, but
           English-centric — Korean answers are rough. Kept for low-end/English use.

RAG-only (the agentic tool-loop is Gemini-native). Honest tradeoff: small local
models are weaker than a frontier API — for top quality, a free Gemini key wins.
Binaries: github.com/PrismML-Eng/llama.cpp · models: huggingface.co.
"""
from __future__ import annotations

import os
import platform
import signal
import subprocess
import sys
import tarfile
import time
import urllib.request
import zipfile
from pathlib import Path

PORT = 8284                       # loopback OpenAI server (distinct from serve 8282)
PROVIDER = "local"                # the providers.py chat-provider id pointing here
DEFAULT_MODEL = "exaone"
_REL = "prism-b8846-d104cf1"      # PrismML-Eng/llama.cpp release (Q2_0 kernels + recent archs)
_BASE = f"https://github.com/PrismML-Eng/llama.cpp/releases/download/{_REL}"
_HF = "https://huggingface.co"

# key → model spec. ``flags`` are extra llama-server args; ``min_mb`` is a
# completed-download sanity floor.
MODELS: dict[str, dict] = {
    "exaone": {"label": "EXAONE 3.5 2.4B — Korean-native (recommended)",
               "file": "EXAONE-3.5-2.4B-Instruct-Q4_K_M.gguf",
               "url": f"{_HF}/LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct-GGUF/resolve/main/EXAONE-3.5-2.4B-Instruct-Q4_K_M.gguf",
               "min_mb": 800, "flags": []},
    "qwen3":  {"label": "Qwen3 1.7B — multilingual",
               "file": "Qwen3-1.7B-Q8_0.gguf",
               "url": f"{_HF}/Qwen/Qwen3-1.7B-GGUF/resolve/main/Qwen3-1.7B-Q8_0.gguf",
               "min_mb": 800, "flags": ["--reasoning", "off"]},   # reply directly, no <think>
    "bonsai": {"label": "Bonsai 1.7B — ternary, ultralight (English; weak Korean)",
               "file": "Ternary-Bonsai-1.7B-Q2_0.gguf",
               "url": f"{_HF}/prism-ml/Ternary-Bonsai-1.7B-gguf/resolve/main/Ternary-Bonsai-1.7B-Q2_0.gguf",
               "min_mb": 200, "flags": []},
}


def _asset() -> tuple[str, str]:
    """(release-asset filename, archive kind) of the CPU server build for this OS/arch."""
    arm = platform.machine().lower() in ("arm64", "aarch64")
    if os.name == "nt":   # Windows uses upstream-style names (no release tag in the asset)
        return (f"llama-bin-win-cpu-{'arm64' if arm else 'x64'}.zip", "zip")
    if sys.platform == "darwin":   # _REL already begins with "prism-" → "llama-{_REL}-…"
        return (f"llama-{_REL}-bin-macos-{'arm64' if arm else 'x64'}.tar.gz", "tar")
    return (f"llama-{_REL}-bin-ubuntu-{'arm64' if arm else 'x64'}.tar.gz", "tar")


def cache_dir() -> Path:
    base = (Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ffs" / "localchat"
            if os.name == "nt" else Path.home() / ".cache" / "ffs" / "localchat")
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
    with (zipfile.ZipFile(arc) if kind == "zip" else tarfile.open(arc)) as a:
        a.extractall(d)
    arc.unlink(missing_ok=True)
    exe = _server_exe(d)
    if exe and os.name != "nt":
        exe.chmod(0o755)
    return exe


def ensure_model(key: str) -> Path:
    """Download the chosen model's GGUF once; cached thereafter."""
    spec = MODELS[key]
    m = cache_dir() / spec["file"]
    if not m.is_file() or m.stat().st_size < spec["min_mb"] * 1024 * 1024:
        _download(spec["url"], m, spec["label"].split(" —")[0])
    return m


def active_model() -> str:
    try:
        k = (cache_dir() / "active.txt").read_text(encoding="utf-8").strip()
        return k if k in MODELS else DEFAULT_MODEL
    except Exception:  # noqa: BLE001
        return DEFAULT_MODEL


def is_up(port: int = PORT) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def stop() -> None:
    """Stop the running server (by recorded PID). Best-effort, cross-platform."""
    pf = cache_dir() / "server.pid"
    try:
        os.kill(int(pf.read_text()), signal.SIGTERM)
        for _ in range(10):
            if not is_up():
                break
            time.sleep(0.5)
    except Exception:  # noqa: BLE001
        pass
    finally:
        pf.unlink(missing_ok=True)


def start(key: str | None = None, port: int = PORT, wait: int = 150) -> bool:
    """Ensure the binary + chosen model are present and a server is serving that
    model. Switches models if a different one is running. Returns True once /health
    responds (model load can take a while on a weak CPU)."""
    key = key or active_model()
    if key not in MODELS:
        key = DEFAULT_MODEL
    if is_up(port):
        if active_model() == key:
            return True
        stop()                                   # switching models → restart
    exe = ensure_binary()
    if not exe:
        return False
    model = ensure_model(key)
    threads = max(1, (os.cpu_count() or 2) - 1)
    args = [str(exe), "-m", str(model), "--host", "127.0.0.1", "--port", str(port),
            "-c", "4096", "-t", str(threads), *MODELS[key]["flags"]]
    log = open(cache_dir() / "server.log", "ab")
    kw: dict = {}
    if os.name == "nt":
        kw["creationflags"] = 0x00000008 | 0x00000200   # DETACHED_PROCESS | NEW_PROCESS_GROUP
    else:
        kw["start_new_session"] = True
    p = subprocess.Popen(args, stdout=log, stderr=log, stdin=subprocess.DEVNULL, **kw)
    (cache_dir() / "server.pid").write_text(str(p.pid), encoding="utf-8")
    (cache_dir() / "active.txt").write_text(key, encoding="utf-8")
    for _ in range(wait):
        if is_up(port):
            return True
        time.sleep(1)
    return is_up(port)
