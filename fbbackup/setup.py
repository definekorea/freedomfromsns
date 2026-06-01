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
        "tier1_hint": "  Optional: turn on smarter (meaning-based) search in the app "
                      "— a one-time local download, or a free key. Keyword search "
                      "already works without it.",
        "tier2_hint": "  Optional: connect an AI in the app to chat with your archive.",
        "opening":   "Opening your archive at {url} …",
        "lang_prompt": "Language / 언어 — [1] English  [2] 한국어 (default {d}): ",
        "no_posts":  "No posts found in that export. Make sure you downloaded "
                     "*Posts* in *JSON* format from Facebook, then unzipped it.",
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
        "tier1_hint": "  선택: 앱에서 더 똑똑한(의미 기반) 검색을 켤 수 있습니다 — "
                      "1회 로컬 다운로드 또는 무료 키. 키워드 검색은 없이도 됩니다.",
        "tier2_hint": "  선택: 앱에서 AI를 연결하면 기록과 대화할 수 있습니다.",
        "opening":   "{url} 에서 기록을 엽니다…",
        "lang_prompt": "Language / 언어 — [1] English  [2] 한국어 (기본 {d}): ",
        "no_posts":  "그 내보내기에서 게시물을 찾지 못했습니다. 페이스북에서 "
                     "*게시물*을 *JSON* 형식으로 받아 압축을 풀었는지 확인하세요.",
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
    if os.name == "nt":  # also scan other drive roots (D:, E:, …)
        import string
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
            if not (n.startswith("facebook-") or ("your" in n and "information" in n)):
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
