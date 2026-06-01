"""FreedomFromSNS — agentic chat: Gemini function-calling over the archive.

Instead of stuffing retrieved context into one prompt (the RAG path in
ffs_api), the model is given TOOLS and drives its own multi-step exploration:
search the archive, open a specific post to read its text and see its REAL
photos/links, preview an external link. Everything it references is grounded in
a tool return — it can't invent a URL because it never writes one.

Photos are handed to the model as opaque refs (img1, img2, …), never URLs, so it
places them by reference (`[[img1]]`) and the real `/api/fb/files` URL + the
source-post-title caption are substituted deterministically afterwards. The
gallery + lightbox payload is the union of every media item any tool returned
this turn. Gemini-only; no Weft, no apicascade.
"""
from __future__ import annotations

import json
import re
import urllib.request

from .embed import gemini_key
from .spaces_backend import _split_frontmatter

_GEM = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
_IMG = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")
_VID = re.compile(r"\[▶[^\]]*\]\(([^)\s]+)\)")
_LINK = re.compile(r"🔗 \[([^\]]+)\]\((https?://[^)\s]+)\)")
_MARKUP = ("#", "![", "🔗", "[▶", "📍", "📘")
_MAX_STEPS = 8

_SYS = (
    "당신은 사용자 본인의 페이스북 기록 보관소를 함께 탐색하는 AI 에이전트입니다. 반드시 도구를 "
    "사용해 답을 찾고, 되묻지 말고 바로 실행하세요.\n"
    "절차:\n"
    "1) search_archive로 질문과 관련된 글을 찾습니다.\n"
    "2) 사용자가 사진·영상을 보고 싶어 하거나 특정 기록을 묻는다면, 관련 글들(보통 3~6개)을 "
    "get_post로 직접 열어 본문과 실제 사진 ref를 가져옵니다. '보여드릴까요?'라고 되묻지 말고 바로 "
    "여세요.\n"
    "3) 외부 링크가 궁금하면 get_link_preview로 미리보기를 봅니다.\n"
    "사진을 본문에 보여주려면 URL을 직접 쓰지 말고, get_post가 돌려준 각 사진의 ref를 그대로 써서 "
    "[[ref]] 형식으로 넣으세요(예: [[img1]]). 사용자가 사진을 보고 싶어 하면 관련 사진을 여러 장 "
    "[[ref]]로 본문에 넣어 실제로 보여주세요. 당신은 이미지를 볼 수 없으니 사진이 무엇을 담았는지 "
    "추측해 묘사하지 말고, 날짜·맥락만 설명하세요. 한국어로 충실하고 완결된 답을 쓰고, 관련 기록을 "
    "찾지 못하면 솔직히 말하세요."
)

_TOOLS = [{"functionDeclarations": [
    {"name": "search_archive",
     "description": "사용자의 페이스북 기록을 의미 기반으로 검색해 관련 글 목록(id·날짜·제목·유형·요약)을 돌려준다. 사진/영상/주제를 찾을 때 먼저 호출한다.",
     "parameters": {"type": "object", "properties": {
         "query": {"type": "string", "description": "자연어 검색어 (예: '여행 사진', '비트코인')"},
         "type": {"type": "string", "enum": ["photo", "video", "link", "status"], "description": "글 유형 필터(선택)"},
         "year": {"type": "string", "description": "연도 YYYY 필터(선택)"}},
         "required": ["query"]}},
    {"name": "get_post",
     "description": "글 하나의 전체 본문과 그 글에 포함된 사진/영상(각 ref 포함)·링크를 돌려준다. 사진을 보여주려면 여기서 받은 ref를 써야 한다.",
     "parameters": {"type": "object", "properties": {
         "id": {"type": "string", "description": "search_archive가 돌려준 글 id"}},
         "required": ["id"]}},
    {"name": "get_link_preview",
     "description": "외부 링크의 미리보기(제목·설명·이미지·사이트)를 돌려준다.",
     "parameters": {"type": "object", "properties": {
         "url": {"type": "string"}}, "required": ["url"]}},
]}]


def _plain(body: str) -> str:
    out = [s for line in body.splitlines()
           if (s := line.strip()) and not s.startswith(_MARKUP)]
    return " ".join(" ".join(out).split())


class _Turn:
    """Per-turn tool dispatcher + media-ref registry (grounds the model)."""

    def __init__(self, b):
        self.b = b
        self.media: dict[str, dict] = {}   # ref → {url,type,post_id,post_title}
        self._by_url: dict[str, str] = {}
        self._n = 0
        self.sources: dict[str, str] = {}  # post id → title

    def _ref(self, url: str, typ: str, post_id: str, title: str) -> str:
        if url in self._by_url:
            return self._by_url[url]
        self._n += 1
        ref = f"img{self._n}"
        self.media[ref] = {"url": url, "type": typ, "post_id": post_id, "post_title": title}
        self._by_url[url] = ref
        return ref

    def _file(self, post_id: str):
        try:
            ws, rel = self.b._parse_object_id(post_id)
            full = self.b._validate_path(ws, rel)
            return full if full.is_file() else None
        except Exception:  # noqa: BLE001
            return None

    # ── tools ─────────────────────────────────────────────────────────────
    def search_archive(self, query: str, type: str | None = None, year: str | None = None) -> dict:
        query = (query or "").strip()
        if not query:
            return {"results": []}
        rows = self.b._semantic(query, "default", k=14) or []
        if not rows:
            toks = [t for t in query.lower().split() if t]
            rows = [r for r in self.b._ensure_index("default")["rows"]
                    if toks and all(t in r["_blob"] for t in toks)][:14]
        out = []
        for r in rows:
            p = r["props"]
            if type and str(p.get("type")) != type:
                continue
            if year and not str(p.get("date", "")).startswith(year):
                continue
            self.sources[r["id"]] = r["title"]
            out.append({"id": r["id"], "date": str(p.get("date", "")), "title": r["title"],
                        "type": str(p.get("type", "")), "snippet": (r["summary"] or "")[:160]})
            if len(out) >= 8:
                break
        return {"results": out}

    def get_post(self, id: str) -> dict:
        full = self._file(id)
        if not full:
            return {"error": "not found", "id": id}
        props, body = _split_frontmatter(full.read_text(encoding="utf-8", errors="replace"))
        title = next((l[2:].strip() for l in body.splitlines() if l.startswith("# ")),
                     str(props.get("title", "")))
        self.sources[id] = title
        photos = [{"ref": self._ref(m.group(2), "image", id, title), "caption": m.group(1)}
                  for m in _IMG.finditer(body)]
        videos = [{"ref": self._ref(m.group(1), "video", id, title), "caption": ""}
                  for m in _VID.finditer(body)]
        links = [{"url": m.group(2), "name": m.group(1)} for m in _LINK.finditer(body)]
        return {"id": id, "date": str(props.get("date", "")), "title": title,
                "text": _plain(body)[:1200], "photos": photos, "videos": videos, "links": links}

    def get_link_preview(self, url: str) -> dict:
        u = self.b._unfurl(url or "")
        return {"ok": bool(u.get("ok")), "title": u.get("title", ""),
                "description": u.get("description", ""), "image": u.get("image", ""),
                "site": u.get("site", "")}

    def dispatch(self, name: str, args: dict) -> dict:
        try:
            if name == "search_archive":
                return self.search_archive(args.get("query", ""), args.get("type"), args.get("year"))
            if name == "get_post":
                return self.get_post(args.get("id", ""))
            if name == "get_link_preview":
                return self.get_link_preview(args.get("url", ""))
        except Exception as e:  # noqa: BLE001
            return {"error": str(e)[:140]}
        return {"error": f"unknown tool {name}"}

    # ── post-processing ───────────────────────────────────────────────────
    def apply(self, text: str) -> str:
        used: set[str] = set()

        def _mk(m):
            ref = m.group(1)
            if ref in self.media and ref not in used:
                used.add(ref)
                it = self.media[ref]
                return f"![{it['post_title']}]({it['url']})"
            return ""
        text = re.sub(r"\[\[\s*(img\d+)\s*\]\]", _mk, text)
        allowed = {it["url"] for it in self.media.values()}
        text = _IMG.sub(lambda m: m.group(0) if m.group(2) in allowed else "", text)
        return re.sub(r"\n{3,}", "\n\n", text).strip()

    def media_list(self) -> list[dict]:
        return list(self.media.values())[:80]

    def source_list(self) -> list[dict]:
        return [{"id": i, "title": t} for i, t in self.sources.items()][:20]


def _err_message(e: Exception) -> str:
    """Turn a failed Gemini call into a clear, actionable message — surface the
    API's OWN error text (the real reason) and flag a rejected key, instead of a
    bare 'HTTP Error 403'."""
    import urllib.error
    if isinstance(e, urllib.error.HTTPError):
        detail = ""
        try:
            raw = e.read().decode("utf-8", "replace")[:600]
            err = (json.loads(raw) or {}).get("error")
            detail = (err.get("message") if isinstance(err, dict) else err) or raw
        except Exception:  # noqa: BLE001
            pass
        if e.code in (401, 403):
            return (f"Gemini 키가 거부되었습니다 (HTTP {e.code}) — 키가 맞는지, 그리고 Generative "
                    f"Language API가 활성화됐는지 확인하세요. / Gemini rejected the key (HTTP {e.code}) — "
                    f"check the key and that the Generative Language API is enabled. [{str(detail)[:200]}]")
        return f"Gemini API 오류 (HTTP {e.code}). [{str(detail)[:200]}]"
    return f"지금은 답변을 생성하지 못했습니다. ({str(e)[:140]})"


def _call(model: str, key: str, contents: list, use_tools: bool = True) -> dict:
    from .ffs_api import lane_generation_config   # same per-lane thinking policy
    payload = {"systemInstruction": {"parts": [{"text": _SYS}]}, "contents": contents,
               "generationConfig": lane_generation_config(model, 0.4)}
    if use_tools:
        payload["tools"] = _TOOLS
    body = json.dumps(payload).encode()
    req = urllib.request.Request(_GEM.format(model=model, key=key), data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def agent_chat(b, messages: list[dict], model: str) -> dict:
    """Run the function-calling loop and return {answer, sources, media, model, steps}."""
    turn = _Turn(b)
    key = gemini_key()
    if not key:
        return {"answer": "AI 대화에는 Gemini API 키가 필요합니다 — 설정에서 무료 키를 연결하세요 "
                          "(https://aistudio.google.com/apikey). / AI chat needs a Gemini API key — "
                          "connect a free one in Settings.",
                "sources": [], "media": [], "model": model, "steps": 0}
    contents = [{"role": "model" if m.get("role") == "assistant" else "user",
                 "parts": [{"text": (m.get("content") or "").strip()}]}
                for m in messages if (m.get("content") or "").strip()]
    if not contents:
        contents = [{"role": "user", "parts": [{"text": "안녕하세요"}]}]

    text, steps = "", 0
    for steps in range(1, _MAX_STEPS + 1):
        try:
            resp = _call(model, key, contents, use_tools=True)
        except Exception as e:  # noqa: BLE001
            return {"answer": _err_message(e),
                    "sources": turn.source_list(), "media": turn.media_list(),
                    "model": model, "steps": steps}
        cand = (resp.get("candidates") or [{}])[0]
        parts = (cand.get("content") or {}).get("parts") or []
        calls = [p["functionCall"] for p in parts if "functionCall" in p]
        if not calls:
            text = "".join(p.get("text", "") for p in parts)
            break
        contents.append(cand["content"])
        contents.append({"role": "function", "parts": [
            {"functionResponse": {"name": c["name"], "response": turn.dispatch(c["name"], c.get("args", {}) or {})}}
            for c in calls]})
    if not text:  # ran out of steps still calling tools → force a final summary
        try:
            resp = _call(model, key, contents, use_tools=False)
            parts = ((resp.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
            text = "".join(p.get("text", "") for p in parts)
        except Exception:  # noqa: BLE001
            pass

    return {"answer": turn.apply(text) or "지금은 답변을 생성하지 못했습니다.",
            "sources": turn.source_list(), "media": turn.media_list(),
            "model": model, "steps": steps}
