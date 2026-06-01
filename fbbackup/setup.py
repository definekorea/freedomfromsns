"""ffs setup — the first-run wizard's building blocks.

The goal (see docs/deployment-and-publishing.md §0–4): get the user's archive on
screen with the *fewest possible questions* — pick a language, auto-locate the
Facebook export, then `parse → build` and open the browser at **Tier 0** (browse
+ keyword search, no key, no model download). Semantic search (Tier 1) and chat
(Tier 2) are optional unlocks surfaced in-app, never gates here.

This module holds the pure, testable pieces (i18n strings, export auto-locate,
config writing, unzip); the interactive flow lives in ``cli.cmd_setup``.
"""
from __future__ import annotations

import os
import re
import shutil
import sys
import zipfile
from pathlib import Path

# ── i18n ──────────────────────────────────────────────────────────────────────
# Bilingual KO+EN is a North Star commitment (docs/principles.md §1). The wizard
# is the first thing a user sees, so it speaks their language from line one.
STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "welcome":   "FreedomFromSNS — let's bring your Facebook archive to life.",
        "searching": "Looking for your Facebook download…",
        "found_one": "Found your export: {path}",
        "found_many": "Found {n} possible exports — newest first:",
        "none_found": "Couldn't find a Facebook export automatically.",
        "enter_path": "Enter the path to your unzipped export (the folder that "
                      "contains a 'facebook-…' folder), or leave blank to cancel: ",
        "not_export": "That folder doesn't look like a Facebook export "
                      "(no */your_facebook_activity/posts inside).",
        "unzipping": "Unzipping {path} …",
        "using":     "Using export: {path}",
        "data_place": "Use it where it is, or move it into ~/ffs/data? "
                      "[1] keep it here (default)  [2] move it in: ",
        "moving":    "Moving your export into ~/ffs/data …",
        "parsing":   "Reading your posts…",
        "building":  "Building your timeline…",
        "parsed":    "Read {n} posts.",
        "built":     "Timeline ready ({n} entries).",
        "tier0":     "✓ Your archive is ready — browse, filter, and keyword search "
                     "work now, with no AI key needed.",
        "smart_offer": "Smarter (meaning-based) search & AI chat are optional — "
                       "browsing and keyword search already work without any key.",
        "hw_gpu":   "  GPU detected: {name}. It can run a local model fast — no key needed.",
        "hw_cpu":   "  No GPU detected. A local model still runs on the CPU (slower); "
                    "for speed a free AI API key is recommended.",
        "choose_embed": "Enable smart search? [1] local model (no key)  "
                        "[2] AI API key (Gemini)  [3] skip for now (default {d}): ",
        "installing_local": "Installing the local model components (one time, a few minutes)…",
        "install_fail": "Couldn't install the local model automatically — skipping. "
                        "Browsing still works; enable smart search later in the app.",
        "ask_gemini_key": "Paste a Gemini API key (free: https://aistudio.google.com/apikey), "
                          "or leave blank to skip: ",
        "embed_started": "Building the smart-search index in the background (see embed.log) "
                         "— browse while it runs.",
        "microbench": "Testing embedding speed on your hardware…",
        "embed_started_est": "Building the smart-search index in the background "
                             "(~{min} min on your hardware; see embed.log) — browse while it runs.",
        "backoff_slow": "On this hardware, local smart search would take ~{min} min. "
                        "Browsing + keyword search work now; for fast meaning-based search, "
                        "connect a free AI key in the app (skipped the local model for now).",
        "embed_skip": "Skipped. You can enable smart search & chat anytime in the app.",
        "tn_downloading_cf": "Downloading cloudflared (one time, ~35 MB)…",
        "tn_need_cf": "Couldn't get cloudflared automatically. Install it:",
        "tn_intro":  "A permanent address lives on your own domain (e.g. archive.yourname.com) and "
                     "survives restarts. You need a FREE Cloudflare account and a domain whose DNS "
                     "is on Cloudflare. (Don't have one? Register a cheap domain and add it to "
                     "Cloudflare's free plan — https://dash.cloudflare.com/sign-up)",
        "tn_login":  "Opening a browser to log in to Cloudflare — pick the domain you added…",
        "tn_login_fail": "Not logged in to Cloudflare — run `ffs tunnel` again after logging in.",
        "tn_ask_host": "Enter the address you want (e.g. archive.yourname.com): ",
        "tn_plan":   "Dry run — these steps would run (nothing changed):",
        "tn_create_fail": "Couldn't create the tunnel. Check your Cloudflare login and try again.",
        "tn_route":  "Pointing {host} at your tunnel…",
        "tn_route_fail": "Couldn't route DNS — is {host}'s domain on your Cloudflare account?",
        "tn_ready":  "✓ Permanent address ready: https://{host}  (config: {cfg})",
        "tn_run_hint": "Start it any time with — keep it running for the address to work:",
        "tn_running": "Running the tunnel now (Ctrl-C to stop)…",
        "tn_service": "For an always-on address (survives reboots), install it as a service: "
                      "`cloudflared --config {cfg} service install`.",
        "opening":   "Opening your archive at {url} …",
        "shortcut_made": "Created a launcher: {path}\n  Double-click it any time to reopen your archive.",
        "autostart_offer": "Start FreedomFromSNS automatically when you log in? [y/N]: ",
        "autostart_on": "Auto-start at login is ON.",
        "lang_prompt": "Language / 언어 — [1] English  [2] 한국어 (default {d}): ",
        "no_posts":  "No posts found in that export. Make sure you downloaded "
                     "*Posts* in *JSON* format from Facebook, then unzipped it.",
        "no_data_guide": "No Facebook export found yet — that's fine, the app is installed.\n"
                         "  1) Request your data: Accounts Center → Your information and\n"
                         "     permissions → Export your information → Format JSON, All time.\n"
                         "     (Meta emails you when it's ready — often 1–3 days.)\n"
                         "  2) When the .zip is in your Downloads, double-click the\n"
                         "     \"FreedomFromSNS (Add data)\" icon on your Desktop — or just run\n"
                         "     `ffs setup` again. It'll find the file automatically.",
        "add_data_made": "Added a \"FreedomFromSNS (Add data)\" launcher: {path}",
        "choose":    "Pick a number (default 1): ",
    },
    "ko": {
        "welcome":   "FreedomFromSNS — 당신의 페이스북 기록을 되살려 봅시다.",
        "searching": "페이스북 다운로드 파일을 찾는 중…",
        "found_one": "내보내기 폴더를 찾았습니다: {path}",
        "found_many": "가능한 내보내기 {n}개를 찾았습니다 — 최신순:",
        "none_found": "페이스북 내보내기를 자동으로 찾지 못했습니다.",
        "enter_path": "압축을 푼 내보내기 폴더('facebook-…' 폴더가 들어 있는 상위 "
                      "폴더) 경로를 입력하세요. 취소하려면 빈 칸으로 두세요: ",
        "not_export": "그 폴더는 페이스북 내보내기로 보이지 않습니다 "
                      "(*/your_facebook_activity/posts 없음).",
        "unzipping": "{path} 압축을 푸는 중…",
        "using":     "사용할 내보내기: {path}",
        "data_place": "현재 위치에서 그대로 쓸까요, ~/ffs/data로 옮길까요? "
                      "[1] 그대로 두기(기본)  [2] 옮기기: ",
        "moving":    "내보내기를 ~/ffs/data로 옮기는 중…",
        "parsing":   "게시물을 읽는 중…",
        "building":  "타임라인을 만드는 중…",
        "parsed":    "게시물 {n}개를 읽었습니다.",
        "built":     "타임라인 준비 완료 (항목 {n}개).",
        "tier0":     "✓ 기록 준비 완료 — 둘러보기, 필터, 키워드 검색이 AI 키 없이 "
                     "바로 됩니다.",
        "smart_offer": "더 똑똑한(의미 기반) 검색과 AI 대화는 선택입니다 — "
                       "둘러보기·키워드 검색은 키 없이도 이미 됩니다.",
        "hw_gpu":   "  GPU 감지됨: {name}. 로컬 모델을 빠르게 돌릴 수 있어요 — 키 불필요.",
        "hw_cpu":   "  GPU가 없습니다. 로컬 모델은 CPU로도 되지만(느림), 빠르게 하려면 "
                    "무료 AI API 키를 권장합니다.",
        "choose_embed": "스마트 검색을 켤까요? [1] 로컬 모델(키 불필요)  "
                        "[2] AI API 키(Gemini)  [3] 지금은 건너뛰기 (기본 {d}): ",
        "installing_local": "로컬 모델 구성요소를 설치하는 중… (최초 1회, 몇 분 걸릴 수 있어요)",
        "install_fail": "로컬 모델 자동 설치에 실패해 건너뜁니다. 둘러보기는 그대로 되고, "
                        "나중에 앱에서 스마트 검색을 켤 수 있어요.",
        "ask_gemini_key": "Gemini API 키를 붙여넣으세요(무료 발급: https://aistudio.google.com/apikey). "
                          "건너뛰려면 비워 두세요: ",
        "embed_started": "백그라운드에서 스마트 검색 색인을 만드는 중입니다(embed.log) "
                         "— 그 사이 자유롭게 둘러보세요.",
        "microbench": "이 컴퓨터에서 임베딩 속도를 측정하는 중…",
        "embed_started_est": "백그라운드에서 스마트 검색 색인을 만드는 중입니다"
                             "(이 컴퓨터 기준 약 {min}분; embed.log) — 그 사이 둘러보세요.",
        "backoff_slow": "이 컴퓨터에서는 로컬 스마트 검색에 약 {min}분이 걸립니다. "
                        "둘러보기·키워드 검색은 지금 바로 되고, 빠른 의미 검색을 원하면 "
                        "앱에서 무료 AI 키를 연결하세요(로컬 모델은 일단 건너뜀).",
        "embed_skip": "건너뛰었습니다. 스마트 검색·AI 대화는 언제든 앱에서 켤 수 있어요.",
        "tn_downloading_cf": "cloudflared를 내려받는 중입니다(최초 1회, 약 35 MB)…",
        "tn_need_cf": "cloudflared를 자동으로 받지 못했습니다. 직접 설치:",
        "tn_intro":  "고정 주소는 내 도메인(예: archive.yourname.com)으로 제공되며 재시작해도 "
                     "유지됩니다. **무료 Cloudflare 계정**과 **DNS가 Cloudflare에 등록된 도메인**이 "
                     "필요합니다. (없다면 저렴한 도메인을 사서 Cloudflare 무료 플랜에 추가하세요 — "
                     "https://dash.cloudflare.com/sign-up)",
        "tn_login":  "Cloudflare 로그인을 위해 브라우저를 엽니다 — 추가해 둔 도메인을 선택하세요…",
        "tn_login_fail": "Cloudflare에 로그인되지 않았습니다 — 로그인 후 `ffs tunnel`을 다시 실행하세요.",
        "tn_ask_host": "원하는 주소를 입력하세요(예: archive.yourname.com): ",
        "tn_plan":   "미리보기 — 아래 단계가 실행됩니다(아무것도 바꾸지 않음):",
        "tn_create_fail": "터널을 만들지 못했습니다. Cloudflare 로그인 상태를 확인하고 다시 시도하세요.",
        "tn_route":  "{host} 주소를 터널에 연결하는 중…",
        "tn_route_fail": "DNS 연결에 실패했습니다 — {host}의 도메인이 내 Cloudflare 계정에 있나요?",
        "tn_ready":  "✓ 고정 주소 준비 완료: https://{host}  (설정: {cfg})",
        "tn_run_hint": "다음 명령으로 실행하세요 — 주소가 작동하려면 켜져 있어야 합니다:",
        "tn_running": "지금 터널을 실행합니다(Ctrl-C로 중지)…",
        "tn_service": "재부팅에도 항상 켜두려면 서비스로 설치하세요: "
                      "`cloudflared --config {cfg} service install`.",
        "opening":   "{url} 에서 기록을 엽니다…",
        "shortcut_made": "바로가기를 만들었습니다: {path}\n  더블클릭하면 언제든 기록을 다시 열 수 있어요.",
        "autostart_offer": "로그인할 때 FreedomFromSNS를 자동으로 시작할까요? [y/N]: ",
        "autostart_on": "로그인 시 자동 시작이 켜졌습니다.",
        "lang_prompt": "Language / 언어 — [1] English  [2] 한국어 (기본 {d}): ",
        "no_posts":  "그 내보내기에서 게시물을 찾지 못했습니다. 페이스북에서 "
                     "*게시물*을 *JSON* 형식으로 받아 압축을 풀었는지 확인하세요.",
        "no_data_guide": "아직 페이스북 데이터를 찾지 못했어요 — 괜찮아요, 앱은 설치됐습니다.\n"
                         "  1) 데이터 신청: 어카운트 센터 → 내 정보 및 권한 → 정보 내보내기\n"
                         "     → 형식 JSON, 전체 기간. (준비되면 이메일이 옵니다 — 보통 1~3일.)\n"
                         "  2) 받은 .zip이 다운로드 폴더에 있으면, 바탕화면의\n"
                         "     \"FreedomFromSNS (Add data)\" 아이콘을 더블클릭하세요 — 또는\n"
                         "     `ffs setup`을 다시 실행하면 파일을 자동으로 찾습니다.",
        "add_data_made": "\"FreedomFromSNS (Add data)\" 바로가기를 만들었어요: {path}",
        "choose":    "번호를 고르세요 (기본 1): ",
    },
}


def t(lang: str, key: str, **kw) -> str:
    """Localized string; falls back to English for any missing key/lang."""
    s = STRINGS.get(lang, STRINGS["en"]).get(key) or STRINGS["en"][key]
    return s.format(**kw) if kw else s


def detect_lang() -> str:
    """Best-effort UI language from the OS locale. Korean if the locale starts
    with 'ko', else English (the safe default for the widest audience)."""
    for var in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        v = os.environ.get(var, "")
        if v:
            return "ko" if v.lower().startswith("ko") else "en"
    if os.name == "nt":  # Windows: no LANG — ask the OS
        try:
            import locale
            loc = (locale.getdefaultlocale()[0] or "")
            return "ko" if loc.lower().startswith("ko") else "en"
        except Exception:  # noqa: BLE001
            pass
    return "en"


# ── auto-locate the Facebook export ─────────────────────────────────────────────
def _has_export(folder: Path) -> bool:
    """The load-bearing marker: a real export folder has your_facebook_activity/posts."""
    try:
        return (folder / "your_facebook_activity" / "posts").is_dir()
    except OSError:
        return False


def search_roots() -> list[Path]:
    """Where downloads usually land, per-OS. Cheap, shallow — we only glob a level
    or two in each (no full-disk walk)."""
    home = Path.home()
    roots = [home / "Downloads", home / "Desktop", home / "Documents", home, Path.cwd()]
    if os.name == "nt":
        od = home / "OneDrive"   # Desktop/Documents/Downloads are often redirected into OneDrive
        roots += [od / "Downloads", od / "Desktop", od / "Documents"]
        import string             # also scan other drive roots (D:, E:, …)
        roots += [Path(f"{d}:/") for d in string.ascii_uppercase if Path(f"{d}:/").exists()]
    return roots


def locate_export(extra_roots: list[Path] | None = None) -> list[dict]:
    """Find candidate Facebook exports under the usual download locations.

    Returns dicts ``{kind, root, marker?, mtime}`` newest-first:
      - ``kind='folder'`` → ``root`` is the PARENT dir to set as [export].root
        (``parse`` iterates its subfolders for ``*/your_facebook_activity/posts``);
        ``marker`` is the matched ``facebook-…`` folder.
      - ``kind='zip'``    → ``root`` is the .zip to offer to unzip.
    """
    roots = list(extra_roots or []) + search_roots()
    seen: set[Path] = set()
    out: list[dict] = []
    for root in roots:
        if not root.is_dir():
            continue
        try:
            children = list(root.iterdir())
        except OSError:
            continue
        # a child folder that IS an export → its parent (root) is the export root
        for cand in children:
            if cand.is_dir() and _has_export(cand):
                er = cand.parent.resolve()
                if er in seen:
                    continue
                seen.add(er)
                out.append({"kind": "folder", "root": er, "marker": cand,
                            "mtime": cand.stat().st_mtime})
        # zips waiting to be extracted
        for z in children:
            if not z.is_file() or z.suffix.lower() != ".zip":
                continue
            n = z.name.lower()
            # Facebook names exports `facebook-<name>-<date>-<hash>.zip`; also accept
            # any zip containing "facebook" or a "your…information" download.
            if not ("facebook" in n or ("your" in n and "information" in n)):
                continue
            zr = z.resolve()
            if zr in seen:
                continue
            seen.add(zr)
            out.append({"kind": "zip", "root": z, "mtime": z.stat().st_mtime})
    out.sort(key=lambda c: c["mtime"], reverse=True)
    return out


def resolve_export_dir(path: Path) -> Path | None:
    """Given a folder the user pointed at (a zip is handled separately), return the
    dir to set as [export].root — the parent that holds a ``facebook-…/your_facebook_
    activity/posts``. Accepts either the ``facebook-…`` folder itself or its parent.
    Returns None if it isn't a Facebook export."""
    path = Path(path)
    if not path.is_dir():
        return None
    if _has_export(path):                                       # pointed AT the facebook-… folder
        return path.parent.resolve()
    try:
        if any(c.is_dir() and _has_export(c) for c in path.iterdir()):  # pointed at the parent
            return path.resolve()
    except OSError:
        pass
    return None


def is_within(child: Path, parent: Path) -> bool:
    try:
        Path(child).resolve().relative_to(Path(parent).resolve())
        return True
    except (ValueError, OSError):
        return False


def relocate_export(export_root: Path, home: Path) -> Path:
    """Move the ``facebook-…`` folder(s) under ``export_root`` into ``~/ffs/data`` so
    the whole archive lives in one place, and return ``~/ffs/data`` (the new root).
    Only the export folders move — unrelated siblings are left alone."""
    dest = home / "data"
    dest.mkdir(parents=True, exist_ok=True)
    for child in list(Path(export_root).iterdir()):
        if child.is_dir() and _has_export(child):
            target = dest / child.name
            if target.resolve() != child.resolve():
                shutil.move(str(child), str(target))
    return dest.resolve()


def unzip_export(zip_path: Path, dest_parent: Path) -> Path:
    """Extract a Facebook .zip into ``dest_parent/data/`` (i.e. ``~/ffs/data``) and
    return the export root (the dir to set as [export].root — the PARENT of the
    ``facebook-…`` folder, since ``parse`` scans subfolders). Re-extracting
    overwrites in place."""
    dest = dest_parent / "data"
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest)
    # Real exports extract a top-level ``facebook-…/`` folder → ``dest`` is the
    # parent ``parse`` expects.
    if any(c.is_dir() and _has_export(c) for c in dest.iterdir()):
        return dest.resolve()
    # Unusual: the activity tree landed directly at the top of ``dest`` → wrap it
    # in a folder so ``parse``'s subfolder scan finds it.
    if _has_export(dest):
        wrap = dest / "facebook-export"
        wrap.mkdir(exist_ok=True)
        for item in list(dest.iterdir()):
            if item != wrap:
                item.rename(wrap / item.name)
    return dest.resolve()


# ── write the chosen export path into config.toml ───────────────────────────────
_TEMPLATE = (
    '# FreedomFromSNS — config. Paths use forward slashes.\n'
    '[export]\n'
    '# Root of the unzipped Facebook download (READ-ONLY; never modified).\n'
    'root = "{root}"\n'
    '[output]\n'
    'dir = "index"\n'
    '[serve]\n'
    'host = "127.0.0.1"\n'
    'port = 8282\n'
)


# ── hardware probe + optional semantic-search setup (Tier 1) ───────────────────
def detect_gpu() -> dict:
    """Best-effort NVIDIA GPU probe via nvidia-smi → {gpu, name, vram_mb}."""
    import subprocess
    exe = shutil.which("nvidia-smi")
    if not exe:
        return {"gpu": False, "name": "", "vram_mb": 0}
    try:
        out = subprocess.run([exe, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=8)
        name, mem = (s.strip() for s in (out.stdout or "").strip().splitlines()[0].split(","))
        return {"gpu": True, "name": name, "vram_mb": int(float(mem))}
    except Exception:  # noqa: BLE001
        return {"gpu": False, "name": "", "vram_mb": 0}


def _available_mb() -> int:
    """Available (not total) RAM in MB — the load-bearing number for the tester.
    Cross-platform, stdlib only. 0 if it can't be read."""
    try:
        if os.name == "nt":
            import ctypes

            class _MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            ms = _MS(); ms.dwLength = ctypes.sizeof(_MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
            return int(ms.ullAvailPhys) // (1024 * 1024)
        mi = Path("/proc/meminfo")
        if mi.exists():                                   # Linux
            for line in mi.read_text().splitlines():
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) // 1024
        import subprocess                                 # macOS (total ≈ avail, good enough)
        r = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5)
        return int(r.stdout.strip()) // (1024 * 1024)
    except Exception:  # noqa: BLE001
        return 0


def _ort_providers() -> list[str]:
    """Accelerators onnxruntime can actually use (empty until it's installed)."""
    try:
        import onnxruntime
        return list(onnxruntime.get_available_providers())
    except Exception:  # noqa: BLE001
        return []


def detect_hardware() -> dict:
    """GPU/CPU/RAM summary + a recommendation: 'local' when a CUDA GPU or Apple
    Silicon is present (fast embeddings), else 'key' (local CPU embedding of a big
    archive is slow). The micro-benchmark refines this empirically before committing."""
    import platform
    g = detect_gpu()
    apple = platform.system() == "Darwin" and platform.machine() in ("arm64", "aarch64")
    cuda = g["gpu"] or any("CUDA" in p for p in _ort_providers())
    cores = os.cpu_count() or 1
    avail = _available_mb()
    # local is the default when there's a GPU/Apple Silicon, OR a capable multi-core
    # CPU with headroom (the small model embeds ~24k in minutes there — the micro-
    # benchmark still confirms before the long run). Weak/low-RAM → recommend a key.
    local_ok = cuda or apple or (cores >= 4 and (avail == 0 or avail >= 2000))
    return {**g, "cpu": cores, "apple_silicon": apple, "available_mb": avail,
            "providers": _ort_providers(), "recommend": "local" if local_ok else "key"}


# Curated model selection: which local model fits this machine (or fall to a key).
def recommend_embed(hw: dict) -> dict:
    """Pick from the curated registry by hardware: GPU → 'large', capable → 'mini',
    weak/uncertain → recommend a cloud key. The micro-bench then confirms."""
    from .embed import EMBED_MODELS
    if hw.get("gpu") or any("CUDA" in p for p in hw.get("providers", [])):
        return {"mode": "local", "model_key": "large", "model": EMBED_MODELS["large"]["id"]}
    # Apple Silicon or a normal multi-core CPU → the small multilingual model
    return {"mode": "local", "model_key": "mini", "model": EMBED_MODELS["mini"]["id"]}


def sample_corpus(spaces_root: Path, workspace: str = "default", n: int = 16) -> list[str]:
    """A tiny, representative text sample (incl. a long one) for the micro-benchmark."""
    base = Path(spaces_root) / workspace
    out: list[str] = []
    if not base.is_dir():
        return out
    for ydir in sorted(base.iterdir(), reverse=True):     # newest years first
        if not ydir.is_dir() or ydir.name.startswith("."):
            continue
        for p in sorted(ydir.glob("*.md")):
            t = p.read_text(encoding="utf-8", errors="replace")
            t = re.sub(r"^---\n.*?\n---\n", "", t, flags=re.S)
            lines = [s.strip() for s in t.splitlines()
                     if s.strip() and not s.strip().startswith(("#", "![", "🔗", "[▶", "📍", "📘"))]
            s = " ".join(" ".join(lines).split())
            if len(s) > 40:
                out.append(s[:1200])
            if len(out) >= n:
                return out
    return out


def micro_benchmark(model_id: str, sample: list[str], batch: int = 16, timeout: int = 90) -> dict:
    """Quick empirical probe (in a SUBPROCESS, so an OOM/crash can't take down the
    wizard): load the model, embed the sample, report {ok, tps, peak_mb, dim}. This
    is the only reliable signal — static specs mislead. Returns ok=False on
    timeout/crash (→ the caller backs off to a key)."""
    import json as _json
    import subprocess
    import tempfile
    sf = Path(tempfile.gettempdir()) / "ffs-microbench.json"
    sf.write_text(_json.dumps(sample), encoding="utf-8")
    code = (
        "import json,sys,time\n"
        "from pathlib import Path\n"
        "from fastembed import TextEmbedding\n"
        "s=json.loads(Path(sys.argv[1]).read_text());bs=int(sys.argv[3])\n"
        "m=TextEmbedding(model_name=sys.argv[2])\n"
        "list(m.embed(s[:2],batch_size=bs))\n"
        "t=time.time();v=list(m.embed(s,batch_size=bs));dt=time.time()-t\n"
        "peak=0\n"
        "try:\n"
        " import resource\n"
        " r=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss\n"
        " peak=r//1024 if sys.platform!='darwin' else r//(1024*1024)\n"
        "except Exception: pass\n"
        "print(json.dumps({'tps':round(len(s)/dt,1) if dt else 0,'peak_mb':int(peak),'dim':len(v[0]) if v else 0}))\n"
    )
    try:
        r = subprocess.run([sys.executable, "-c", code, str(sf), model_id, str(batch)],
                           capture_output=True, text=True, timeout=timeout)
        line = (r.stdout or "").strip().splitlines()[-1]
        return {"ok": True, **_json.loads(line)}
    except subprocess.TimeoutExpired:
        return {"ok": False, "reason": "timeout"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": str(e)[:80]}


_MAX_LOCAL_MIN = 30   # if local embedding the whole archive would take longer, back off to a key


def embed_viable(mb: dict, post_count: int, available_mb: int) -> tuple[bool, int]:
    """From a micro-bench result, decide if local embedding is worth it, and the
    estimated minutes for the whole archive. Backs off on failure, projected time
    over ~30 min, or projected peak RAM over ~60% of what's available."""
    if not mb.get("ok"):
        return (False, 0)
    tps = max(float(mb.get("tps") or 0), 0.01)
    est_min = max(1, round(post_count / tps / 60))
    peak = int(mb.get("peak_mb") or 0)
    ram_ok = (available_mb <= 0) or (peak <= 0) or (peak < 0.6 * available_mb)
    return (tps > 0 and est_min <= _MAX_LOCAL_MIN and ram_ok, est_min)


def ensure_local_deps(gpu: bool) -> bool:
    """Make fastembed (+ onnxruntime-gpu for a GPU) importable in THIS interpreter,
    installing via uv (preferred) or pip. Returns True if available afterwards.
    The base install is pure wheels, so the local model is fetched only on demand."""
    import subprocess
    need: list[str] = []
    try:
        import fastembed  # noqa: F401
    except ImportError:
        need.append("fastembed")
    if gpu:
        try:
            import onnxruntime  # noqa: F401
        except ImportError:
            need.append("onnxruntime-gpu")
    if not need:
        return True
    attempts = []
    if shutil.which("uv"):
        attempts.append(["uv", "pip", "install", "--python", sys.executable, *need])
    attempts.append([sys.executable, "-m", "pip", "install", *need])
    for cmd in attempts:
        try:
            if subprocess.run(cmd, timeout=900).returncode == 0:
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def spawn_background_embed(home: Path, provider: str, device: str = "", model: str = "") -> None:
    """Kick off `ffs embed` as a detached background process (logs to embed.log) so
    the semantic index builds while the user browses. Resumable + safe to re-run."""
    import subprocess
    env = dict(os.environ)
    env["FBBACKUP_HOME"] = str(home)
    env["FBBACKUP_EMBED_PROVIDER"] = provider     # force this provider for the corpus
    if device:
        env["FBBACKUP_EMBED_DEVICE"] = device
    if model:
        env["FBBACKUP_EMBED_MODEL"] = model       # the tester-chosen local model
    log = open(home / "embed.log", "ab")
    kw: dict = {}
    if os.name == "nt":
        kw["creationflags"] = 0x00000008 | 0x00000200   # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kw["start_new_session"] = True
    subprocess.Popen([sys.executable, "-m", "fbbackup.cli", "embed"],
                     stdout=log, stderr=log, stdin=subprocess.DEVNULL, env=env, **kw)


def _desktop_dir() -> Path | None:
    """The real Desktop (handles OneDrive-redirected Desktop on Windows)."""
    h = Path.home()
    for c in (h / "Desktop", h / "OneDrive" / "Desktop"):
        if c.is_dir():
            return c
    return None


def create_launcher(home: Path, name: str = "FreedomFromSNS", cli: str = "serve --open") -> Path | None:
    """Write a double-clickable launcher (Desktop if available, else the home dir)
    that runs `ffs <cli>` with FBBACKUP_HOME baked in. Default = one-click relaunch
    (serve + open browser); pass cli='setup' for an "add my data later" launcher."""
    py = sys.executable
    where = _desktop_dir() or home
    try:
        if os.name == "nt":
            f = where / f"{name}.cmd"
            f.write_text("@echo off\r\n"
                         f'set "FBBACKUP_HOME={home}"\r\n'
                         f'"{py}" -m fbbackup.cli {cli}\r\n'
                         "if errorlevel 1 pause\r\n", encoding="utf-8")
        else:
            ext = "command" if sys.platform == "darwin" else "sh"
            f = where / f"{name}.{ext}"
            f.write_text(f'#!/bin/sh\nexport FBBACKUP_HOME="{home}"\n'
                         f'exec "{py}" -m fbbackup.cli {cli}\n', encoding="utf-8")
            f.chmod(0o755)
        return f
    except Exception:  # noqa: BLE001
        return None


def _startup_dir() -> Path | None:
    if os.name == "nt":
        ad = os.environ.get("APPDATA")
        if ad:
            d = Path(ad) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
            if d.is_dir():
                return d
    return None


def enable_autostart(home: Path) -> Path | None:
    """Start the server at login (background, no window). Returns the entry path."""
    py = sys.executable
    try:
        if os.name == "nt":
            sd = _startup_dir()
            if not sd:
                return None
            pyw = Path(py).with_name("pythonw.exe")          # windowless on Windows
            runner = str(pyw if pyw.exists() else py)
            cmd = home / "ffs-server.cmd"
            cmd.write_text("@echo off\r\n"
                           f'set "FBBACKUP_HOME={home}"\r\n'
                           f'"{runner}" -m fbbackup.cli serve\r\n', encoding="utf-8")
            vbs = sd / "FreedomFromSNS.vbs"                   # runs the .cmd hidden at login
            vbs.write_text(f'CreateObject("WScript.Shell").Run """{cmd}""", 0, False\r\n', encoding="utf-8")
            return vbs
        if sys.platform == "darwin":
            la = Path.home() / "Library" / "LaunchAgents"
            la.mkdir(parents=True, exist_ok=True)
            p = la / "com.freedomfromsns.plist"
            p.write_text(
                '<?xml version="1.0" encoding="UTF-8"?>\n<plist version="1.0"><dict>\n'
                '  <key>Label</key><string>com.freedomfromsns</string>\n'
                f'  <key>ProgramArguments</key><array><string>{py}</string><string>-m</string>'
                '<string>fbbackup.cli</string><string>serve</string></array>\n'
                f'  <key>EnvironmentVariables</key><dict><key>FBBACKUP_HOME</key><string>{home}</string></dict>\n'
                '  <key>RunAtLoad</key><true/>\n</dict></plist>\n', encoding="utf-8")
            import subprocess
            try:
                subprocess.run(["launchctl", "load", str(p)], timeout=10)
            except Exception:  # noqa: BLE001
                pass
            return p
        ad = Path.home() / ".config" / "autostart"           # Linux XDG autostart
        ad.mkdir(parents=True, exist_ok=True)
        f = ad / "freedomfromsns.desktop"
        f.write_text("[Desktop Entry]\nType=Application\nName=FreedomFromSNS\n"
                     f'Exec=sh -c \'FBBACKUP_HOME="{home}" "{py}" -m fbbackup.cli serve\'\n'
                     "X-GNOME-Autostart-enabled=true\n", encoding="utf-8")
        return f
    except Exception:  # noqa: BLE001
        return None


def disable_autostart() -> bool:
    try:
        p = None
        if os.name == "nt":
            sd = _startup_dir()
            p = (sd / "FreedomFromSNS.vbs") if sd else None
        elif sys.platform == "darwin":
            p = Path.home() / "Library" / "LaunchAgents" / "com.freedomfromsns.plist"
            if p.exists():
                import subprocess
                try:
                    subprocess.run(["launchctl", "unload", str(p)], timeout=10)
                except Exception:  # noqa: BLE001
                    pass
        else:
            p = Path.home() / ".config" / "autostart" / "freedomfromsns.desktop"
        if p and p.exists():
            p.unlink()
            return True
    except Exception:  # noqa: BLE001
        pass
    return False


def autostart_status() -> bool:
    if os.name == "nt":
        sd = _startup_dir()
        return bool(sd and (sd / "FreedomFromSNS.vbs").exists())
    if sys.platform == "darwin":
        return (Path.home() / "Library" / "LaunchAgents" / "com.freedomfromsns.plist").exists()
    return (Path.home() / ".config" / "autostart" / "freedomfromsns.desktop").exists()


def set_export_root(home: Path, root: Path) -> Path:
    """Write ``[export].root`` into ``home/config.toml`` (replacing any existing
    value, preserving the rest). Creates the file from a template if absent."""
    cfg = home / "config.toml"
    val = str(root).replace("\\", "/")
    if not cfg.is_file():
        cfg.write_text(_TEMPLATE.format(root=val), encoding="utf-8")
        return cfg
    text = cfg.read_text(encoding="utf-8")
    block = re.search(r"(?ms)^\[export\][^\[]*", text)
    if block and re.search(r"(?m)^\s*root\s*=", block.group(0)):
        new_block = re.sub(r"(?m)^\s*root\s*=.*$", f'root = "{val}"', block.group(0), count=1)
        text = text[:block.start()] + new_block + text[block.end():]
    elif block:  # [export] exists but has no root key
        text = text[:block.start()] + f'[export]\nroot = "{val}"\n' + \
            block.group(0)[len("[export]\n"):] + text[block.end():]
    else:  # no [export] table at all
        text = f'[export]\nroot = "{val}"\n\n' + text
    cfg.write_text(text, encoding="utf-8")
    return cfg
