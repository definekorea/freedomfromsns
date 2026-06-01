"""FreedomFromSNS — the SPA-facing API + Gemini-direct RAG chat.

Forks the blog_ask.py RAG (representative-image round-robin, caption-with-
post-title, flat media payload for the lightbox) onto fbbackup's md-row +
embeddings substrate, and talks straight to the **Gemini paid API** — one
provider, one key, no apicascade, no WordPress. Embeddings are produced
offline by `ffs embed`; this module embeds only the live query (reusing
embed.py) and generates the chat answer.

Routes added on top of the SpacesBackend's `/api/fb/*`:
    GET  /api/index            every row as {id,date,title,type,excerpt,thumb}
    POST /api/search  {query}  → {ids:[…]} (semantic + keyword, ranked)
    POST /api/chat    {messages,model} → {answer,sources,media,model}
Post detail reuses the backend's GET /api/fb/objects/{id} (markdown body).
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .embed import gemini_key

# Gemini chat — the two UI-selectable tiers. Embeddings are fixed elsewhere
# (gemini-embedding-001); this is the synthesis model only.
_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
ALLOWED_MODELS = ("gemini-2.5-flash", "gemini-3.1-pro-preview")
DEFAULT_MODEL = os.environ.get("FFS_CHAT_MODEL", "gemini-2.5-flash")

# md-body media/link markup (see spaces_writer.post_to_row): images and videos
# are already `/api/fb/files?path=…` URLs; links are `🔗 [name](http…)`.
_IMG = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")
_VID = re.compile(r"\[▶[^\]]*\]\(([^)\s]+)\)")
_MARKUP = ("#", "![", "🔗", "[▶", "📍", "📘")

_CHAT_SYS = (
    "당신은 사용자 본인의 페이스북 기록 보관소(아카이브)와 대화하는 AI입니다. 매 turn마다 "
    "주어지는 [내 기록 발췌]를 최우선 근거로 삼아, 사용자가 과거에 쓴 글·올린 사진과 영상을 "
    "구체적으로 짚어 가며 깊이 있게 답하세요. 발췌에 날짜가 있으면 자연스럽게 함께 언급하고, "
    "발췌가 질문과 무관하면 솔직히 말한 뒤 일반적인 관점에서 이어가세요. 원하는 만큼 자세히 "
    "한국어로 답하되, 답을 도중에 끊지 말고 반드시 문장을 끝까지 완결하세요."
)


# ── per-post user state: privacy + erase ─────────────────────────────────────
# We never touch the user's data. Per-post decisions (mark private, mark erased)
# live in our OWN sidecars in the index dir, keyed by fb_id, so they survive
# `ffs build` rewriting the markdown. Both are reflected in the display and gate
# the shareable static export.
#   • privacy: FB exports carry no audience, so the parsed default is public; a
#     private post stays visible locally but is excluded from the export.
#   • erased:  a soft delete — hidden from every normal view (recoverable in the
#     trash) and excluded from the export. The data is never deleted.
_OVERRIDES_NAME = "privacy-overrides.json"
_ERASED_NAME = "erased-overrides.json"


def _sidecar(b, name: str):
    return b._index_dir / name


def _load_sidecar(b, name: str) -> dict:
    try:
        return json.loads(_sidecar(b, name).read_text("utf-8")) or {}
    except Exception:  # noqa: BLE001  (missing / unreadable → none)
        return {}


def _save_sidecar(b, name: str, data: dict) -> None:
    p = _sidecar(b, name)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=0), "utf-8")


def load_overrides(b) -> dict:
    return _load_sidecar(b, _OVERRIDES_NAME)


def load_erased(b) -> dict:
    return _load_sidecar(b, _ERASED_NAME)


def effective_privacy(props: dict, overrides: dict, post_id: str) -> str:
    """Override wins over the parsed (always-public) frontmatter value."""
    if post_id in overrides:
        return overrides[post_id]
    return str(props.get("privacy") or "public")


def set_privacy(b, fbids: list, privacy: str) -> dict:
    ov = load_overrides(b)
    for fid in fbids:
        if privacy == "public":
            ov.pop(fid, None)         # public is the default → store sparsely
        else:
            ov[fid] = privacy
    _save_sidecar(b, _OVERRIDES_NAME, ov)
    return ov


def set_erased(b, fbids: list, erased: bool) -> dict:
    ev = load_erased(b)
    for fid in fbids:
        if erased:
            ev[fid] = True
        else:
            ev.pop(fid, None)
    _save_sidecar(b, _ERASED_NAME, ev)
    return ev


def _plain(body: str) -> str:
    """The readable text of a row's md body — drop the H1, image/video/link/place
    markup. Used for the retrieval context (the model can't see images)."""
    out = []
    for line in body.splitlines():
        s = line.strip()
        if not s or s.startswith(_MARKUP):
            continue
        out.append(s)
    return " ".join(" ".join(out).split())


def _media_of(body: str, post_id: str, title: str) -> list[dict]:
    """Flat media list from one row's md body, for the chat gallery + lightbox.
    URLs are the row's own `/api/fb/files?path=…` (served by the backend)."""
    items: list[dict] = []
    for m in _IMG.finditer(body):
        items.append({"url": m.group(2), "type": "image", "post_id": post_id, "post_title": title})
    for m in _VID.finditer(body):
        items.append({"url": m.group(1), "type": "video", "post_id": post_id, "post_title": title})
    return items


def _gemini_chat(messages: list[dict], system: str, model: str, key: str,
                 max_tokens: int = 4096) -> str:
    """One Gemini generateContent call. `messages` is the OpenAI-style dialogue
    (user/assistant); the retrieval context lives in `system`."""
    contents = []
    for m in messages:
        c = (m.get("content") or "").strip()
        if not c:
            continue
        contents.append({"role": "model" if m.get("role") == "assistant" else "user",
                         "parts": [{"text": c}]})
    if not contents:
        contents = [{"role": "user", "parts": [{"text": "안녕하세요"}]}]
    body = json.dumps({
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.5},
    }).encode()
    url = _GEMINI_URL.format(model=model, key=key)
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read())
    cand = (data.get("candidates") or [{}])[0]
    parts = (cand.get("content") or {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts).strip()


def _chat(b, messages: list[dict], model: str) -> dict:
    """RAG: semantic-retrieve over the user's own archive → Gemini synthesis,
    returning {answer, sources, media, model}. `b` is the SpacesBackend."""
    user_turns = [m["content"] for m in messages if m.get("role") == "user" and m.get("content")]
    if not user_turns:
        return {"answer": "질문을 입력해 주세요.", "sources": [], "media": [], "model": model}
    query = " ".join(user_turns[-2:])[:500]

    hits = b._semantic(query, "default", k=12)
    if not hits:  # keyword fallback
        toks = [t for t in query.lower().split() if t]
        hits = [r for r in b._ensure_index("default")["rows"]
                if toks and all(t in r["_blob"] for t in toks)][:12]

    ctx, media, sources = [], [], []
    for r in hits[:12]:
        raw = b._row_text(r)
        title = r["title"]
        text = _plain(raw)[:500]
        ctx.append(f"[{r['props'].get('date', '?')}] {title}: {text}")
        media.extend(_media_of(raw, r["id"], title))
        sources.append({"id": r["id"], "title": title})

    # dedup media by URL (a post can repeat an image), keep order, cap the payload
    seen, flat = set(), []
    for it in media:
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        flat.append(it)
    flat = flat[:80]

    # representative inline images: round-robin across posts (not the first 8 of
    # one post). The model picks WHERE/WHICH by NUMBER only — it never writes a
    # URL (Gemini will happily hallucinate a fake storage.googleapis.com one),
    # so the real URL + the source-post-title caption are substituted here
    # deterministically (Rule 3). The model can't see images; it must not invent
    # what they show — the caption is always the source post's own title.
    by_post: dict[str, list[str]] = {}
    url_title: dict[str, str] = {}
    for it in flat:
        if it["type"] == "image":
            by_post.setdefault(it["post_id"], []).append(it["url"])
            url_title[it["url"]] = it["post_title"]
    inline_urls: list[str] = []
    _round = 0
    while len(inline_urls) < 8 and any(_round < len(v) for v in by_post.values()):
        for v in by_post.values():
            if _round < len(v) and len(inline_urls) < 8:
                inline_urls.append(v[_round])
        _round += 1
    inline = [(u, url_title.get(u, "")) for u in inline_urls]  # (url, title) by index
    inline_lines = ["%d. %s" % (i + 1, t or "(제목 없음)") for i, (u, t) in enumerate(inline)]

    nimg = sum(1 for it in flat if it["type"] == "image")
    nvid = sum(1 for it in flat if it["type"] == "video")
    system = _CHAT_SYS + "\n\n"
    if inline:
        system += (
            f"참고: 관련 기록의 사진 {nimg}장·영상 {nvid}개가 답변 아래 갤러리에 표시되고, "
            "클릭하면 전체 화면으로 넘겨볼 수 있습니다. '사진이 없다'거나 '직접 찾아보라'고 하지 "
            "마세요.\n중요: 당신은 이미지를 직접 볼 수 없습니다. 사진이 무엇을 담았는지 추측해 "
            "묘사하지 마세요(틀립니다). 사진을 본문에 보여주려면 URL을 쓰지 말고, 아래 목록의 "
            "번호만 써서 정확히 [[IMG:번호]] 형식으로 넣으세요(예: [[IMG:1]]). 각 기록의 맥락을 "
            "설명한 뒤 관련 사진 번호를 그 근처에 넣으면 됩니다. 같은 번호를 두 번 쓰지 마세요.\n"
            "[삽입 가능한 사진 — 번호 → 출처 글 제목]\n" + "\n".join(inline_lines) + "\n\n")
    system += ("[내 기록 발췌]\n" + "\n---\n".join(ctx)) if ctx else "[내 기록 발췌] (관련 기록을 찾지 못했습니다.)"

    try:
        answer = _gemini_chat(messages, system, model, gemini_key())
    except Exception as e:  # noqa: BLE001
        return {"answer": f"지금은 답변을 생성하지 못했습니다. ({str(e)[:120]})",
                "sources": sources, "media": flat, "model": model}
    answer = _apply_inline(answer or "지금은 답변을 생성하지 못했습니다.", inline)
    return {"answer": answer, "sources": sources, "media": flat, "model": model}


def _apply_inline(answer: str, inline: list[tuple]) -> str:
    """Replace the model's [[IMG:n]] markers with the real `![title](url)` (the
    URL + source-post-title we control), and strip any image markdown the model
    invented on its own (hallucinated external URLs that wouldn't load)."""
    used: set[int] = set()

    def _marker(m):
        i = int(m.group(1)) - 1
        if 0 <= i < len(inline) and i not in used:
            used.add(i)
            url, title = inline[i]
            return f"![{title}]({url})"
        return ""
    answer = re.sub(r"\[\[\s*IMG\s*:\s*(\d+)\s*\]\]", _marker, answer)
    allowed = {u for u, _ in inline}

    def _drop_hallucinated(m):
        return m.group(0) if m.group(2) in allowed else ""
    answer = _IMG.sub(_drop_hallucinated, answer)
    return re.sub(r"\n{3,}", "\n\n", answer).strip()


def register(app: FastAPI, b) -> None:
    """Mount the SPA-facing routes on `app`, backed by SpacesBackend `b`."""

    @app.get("/api/index")
    def index():
        rows = b._ensure_index("default")["rows"]
        overrides = load_overrides(b)
        erased = load_erased(b)
        out = []
        for r in rows:
            p = r["props"]
            date = str(p.get("date") or "")
            if not date:
                continue
            fbid = str(p.get("fb_id") or "")   # stable key for privacy/erase sidecars
            private = effective_privacy(p, overrides, fbid) != "public"
            thumb, vid = "", bool(p.get("video_path"))
            img = p.get("image_path")
            if img:
                thumb = f"/api/fb/files?path={quote(str(img))}&w=400"
            elif p.get("video_path"):
                thumb = f"/api/fb/vthumb?path={quote(str(p['video_path']))}&w=400"
            ptype = str(p.get("type") or "status")
            out.append({"id": r["id"], "date": date, "title": r["title"],
                        "type": ptype,
                        "excerpt": r["summary"], "preview": r.get("preview", ""),
                        "thumb": thumb, "vid": vid,
                        "link_url": str(p.get("link_url") or ""),
                        # private = excluded from the shareable static export only;
                        # still fully visible in the local browser (a 🔒 badge).
                        "private": private, "fbid": fbid,
                        # erased = soft-deleted: hidden from normal views, shown
                        # only in the trash (recoverable). Data is never deleted.
                        "erased": fbid in erased,
                        # "empty": no media, no link, no real text (title==text) —
                        # nothing to show, hidden from every view. (Reshares are NOT
                        # empty-by-fiat anymore — they live in the 공유 bucket.)
                        "empty": bool(r.get("empty"))})
        out.sort(key=lambda r: r["date"], reverse=True)  # newest first
        return JSONResponse(out)

    def _fbids(body) -> list:
        """Accept either {fbid} (single) or {fbids:[…]} (bulk)."""
        ids = (body or {}).get("fbids")
        if isinstance(ids, list):
            return [str(x) for x in ids if x]
        one = str((body or {}).get("fbid") or "")
        return [one] if one else []

    @app.post("/api/privacy")
    async def privacy(request: Request):
        """Mark posts public/private. Body: {fbid|fbids, privacy:'public'|'private'}.
        Persists to the index-dir sidecar; gates the static export, not local view."""
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            body = {}
        fbids = _fbids(body)
        privacy = str((body or {}).get("privacy") or "public")
        if not fbids:
            return JSONResponse({"error": "no fbid"}, status_code=400)
        if privacy not in ("public", "private"):
            privacy = "public"
        set_privacy(b, fbids, privacy)
        return {"fbids": fbids, "privacy": privacy, "private": privacy != "public", "count": len(fbids)}

    @app.post("/api/erase")
    async def erase(request: Request):
        """Soft-delete / restore posts. Body: {fbid|fbids, erased:true|false}.
        Never deletes data — records the mark in our own sidecar; the post is
        hidden from normal views (recoverable in the trash) and never exported."""
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            body = {}
        fbids = _fbids(body)
        flag = bool((body or {}).get("erased", True))
        if not fbids:
            return JSONResponse({"error": "no fbid"}, status_code=400)
        set_erased(b, fbids, flag)
        return {"fbids": fbids, "erased": flag, "count": len(fbids)}

    @app.post("/api/search")
    async def search(request: Request):
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            body = {}
        q = str((body or {}).get("query", "")).strip()[:300]
        if not q:
            return {"ids": []}
        idx = b._ensure_index("default")
        toks = [t for t in q.lower().split() if t]
        kw = [r for r in idx["rows"] if toks and all(t in r["_blob"] for t in toks)]
        kw.sort(key=lambda r: str(r["props"].get("date", "")), reverse=True)
        ids = [r["id"] for r in kw]
        seen = set(ids)
        for r in b._semantic(q, "default", k=60, exclude=seen):  # enrich with related
            if r["id"] not in seen:
                ids.append(r["id"])
                seen.add(r["id"])
        return {"ids": ids[:400]}

    @app.post("/api/chat")
    async def chat(request: Request):
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            body = {}
        messages = (body or {}).get("messages")
        if not isinstance(messages, list) or not messages:
            return JSONResponse({"error": "empty"}, status_code=400)
        model = str((body or {}).get("model") or DEFAULT_MODEL)
        if model not in ALLOWED_MODELS:
            model = DEFAULT_MODEL
        clean = [{"role": m.get("role"), "content": str(m.get("content", ""))}
                 for m in messages[-12:] if isinstance(m, dict)]
        if (body or {}).get("agent"):  # agentic: Gemini drives its own tool loop
            from .ffs_agent import agent_chat
            return JSONResponse(agent_chat(b, clean, model))
        return JSONResponse(_chat(b, clean, model))  # fast one-shot RAG
