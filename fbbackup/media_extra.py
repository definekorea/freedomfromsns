"""Ingest media that lives OUTSIDE posts — uncategorized photos, uploaded videos,
and photo albums — so the gallery is the user's *whole* archive, not just media
attached to posts. (A real export keeps thousands of photos in
``your_uncategorized_photos.json`` + ``album/`` that no post references.)

Each new media item (deduped by filename against media already in a post) becomes
a synthetic canonical post — same shape as ``parse.normalize_post`` — so it flows
through the existing build → embed → browse pipeline unchanged. Album membership
is surfaced for EVERY post (real or synthetic) whose media is in a named album,
as a ``🗂 앨범: …`` body line, so e.g. searching "Cambodia" finds the whole album.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path

from .mojibake import fix

_VIDEO_EXTS = {".mp4", ".mov", ".webm", ".avi", ".mkv", ".gif"}


def _base(uri: str | None) -> str:
    return os.path.basename(uri or "")


def _items(d) -> list:
    if isinstance(d, list):
        return d
    if isinstance(d, dict):
        for v in d.values():
            if isinstance(v, list):
                return v
    return []


def album_map(posts_dir: Path) -> dict[str, str]:
    """media filename → album name, from ``album/*.json``."""
    out: dict[str, str] = {}
    adir = posts_dir / "album"
    if not adir.is_dir():
        return out
    for af in sorted(adir.glob("*.json")):
        try:
            d = json.load(open(af, encoding="utf-8"))
        except Exception:
            continue
        name = fix(d.get("name", "")) or ""
        if not name:
            continue
        for ph in d.get("photos", []) or []:
            b = _base(ph.get("uri"))
            if b:
                out.setdefault(b, name)
    return out


def _record(item: dict, kind: str, resolve, source: str, album: str = "") -> dict | None:
    uri = item.get("uri", "")
    if not uri:
        return None
    abs_path = resolve(uri)
    cap = fix(item.get("description") or item.get("title")) or ""
    ts = int(item.get("creation_timestamp") or 0)
    return {
        "fb_id": hashlib.sha1(uri.encode()).hexdigest()[:16],
        "timestamp": ts,
        "datetime": datetime.fromtimestamp(ts).isoformat() if ts else "",
        # "uncat" (미분류) — loose media not in any post. A distinct type so the
        # viewer keeps these OUT of the main post timeline (전체) and shows them in
        # their own 미분류 bucket. The media KIND (image/video) is preserved below
        # so the lightbox/detail still renders/plays them correctly.
        "type": "uncat",
        "title": cap or album,
        "group": None,
        "text": cap,
        "hashtags": [],
        "place": None,
        "links": [],
        "media": [{
            "uri": uri,
            "abs_path": str(abs_path) if abs_path else None,
            "kind": kind,
            "caption": cap,
            "creation_timestamp": item.get("creation_timestamp"),
        }],
        "fb_url": "",
        "albums": [],
        "source": source,
    }


def extra_media_posts(posts_dir: Path, seen: set[str], resolve) -> list[dict]:
    """Synthetic posts for album / uncategorized / video media not already in a
    post. ``seen`` is the set of media filenames already used by posts; it's
    mutated so the three sources don't duplicate each other either."""
    recs: list[dict] = []

    def take(items, kind, source, album=""):
        for it in items:
            if not isinstance(it, dict):
                continue
            b = _base(it.get("uri"))
            if not b or b in seen:
                continue
            r = _record(it, kind, resolve, source, album)
            if r:
                seen.add(b)
                recs.append(r)

    adir = posts_dir / "album"
    if adir.is_dir():
        for af in sorted(adir.glob("*.json")):
            try:
                d = json.load(open(af, encoding="utf-8"))
            except Exception:
                continue
            take(d.get("photos", []) or [], "image", "facebook-album", fix(d.get("name", "")) or "")
    f = posts_dir / "your_uncategorized_photos.json"
    if f.is_file():
        try:
            take(_items(json.load(open(f, encoding="utf-8"))), "image", "facebook-uncategorized")
        except Exception:
            pass
    f = posts_dir / "your_videos.json"
    if f.is_file():
        try:
            take(_items(json.load(open(f, encoding="utf-8"))), "video", "facebook-video")
        except Exception:
            pass
    return recs


def apply_albums(records: list[dict], amap: dict[str, str]) -> int:
    """Tag every record whose media is in a named album with that album name.
    Returns how many records were tagged."""
    n = 0
    for r in records:
        names = sorted({amap[_base(m["uri"])] for m in r.get("media", []) if _base(m["uri"]) in amap})
        if names:
            r["albums"] = names
            n += 1
    return n
