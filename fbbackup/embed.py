"""Semantic embeddings for every FB Browser row — pluggable providers.

A public app can't assume any one API key, so embeddings are provider-agnostic
with a no-key LOCAL fallback. Resolution (override via FBBACKUP_EMBED_PROVIDER):

  gemini  — Google `gemini-embedding-001` (best; uses GEMINI_*_API_KEY; paid =
            no rate limits; asymmetric retrieval via taskType)
  local   — fastembed (ONNX, CPU, no key, nothing leaves the machine). Default
            model multilingual MiniLM (see EMBED_MODELS); set FBBACKUP_EMBED_MODEL
            to trade size/quality.

Resolution order with no override: gemini key → local.

Corpus + query MUST use the same provider/model — the choice is recorded in
embed-meta.json and the backend reads it for query-time embedding. Outputs live
in the index dir, OUTSIDE the facebook-data folder. Re-run after download/import.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

GEMINI_MODEL = "gemini-embedding-001"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:embedContent"
LOCAL_MODEL = os.environ.get("FBBACKUP_EMBED_MODEL",
                             "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
# Per-provider score floor for "related" search (chat retrieval uses top-k rank).
THRESHOLDS = {"gemini": 0.62, "local": 0.40}  # local floor depends on the model (see below)

# Curated local embedding models the setup tester picks from — measured on CPU
# (8 vCPU / no GPU): see docs/local-models.md. RULED OUT for auto-selection:
#   jinaai/jina-embeddings-v3, intfloat/multilingual-e5-large — 1024-d, ~2–3.5 h to
#       embed 24k on CPU and up to ~6.9 GB RAM → GPU only;
#   nomic-embed-text-v1.5 — OOMs at large batch, slow on CPU, English-centric;
#   BAAI/bge-small-en-v1.5 — English-only (weak for Korean).
# 'large' is offered only when a GPU is detected.
EMBED_MODELS = {
    "mini":  {"id": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
              "dim": 384, "dl_mb": 240, "multilingual": True, "tier": "cpu",
              "threshold": 0.40, "note": "fast multilingual — the CPU default (~86 texts/s)"},
    "large": {"id": "intfloat/multilingual-e5-large",
              "dim": 1024, "dl_mb": 2240, "multilingual": True, "tier": "gpu",
              "threshold": 0.80, "note": "higher-quality multilingual — needs a GPU"},
}


def local_threshold(model_id: str) -> float:
    """The 'related' score floor for a given local model (similarity scales differ
    by model family). Falls back to the generic local floor."""
    for m in EMBED_MODELS.values():
        if m["id"] == model_id:
            return m["threshold"]
    return THRESHOLDS["local"]


def gemini_key() -> str:
    for var in ("GEMINI_PAID_API_KEY", "GEMINI_FREE_API_KEY", "GEMINI_API_KEY"):
        if os.environ.get(var):
            return os.environ[var]
    return ""


def resolve_provider() -> str:
    forced = os.environ.get("FBBACKUP_EMBED_PROVIDER")
    if forced:
        return forced
    if gemini_key():       # best quality (asymmetric retrieval via taskType)
        return "gemini"
    return "local"         # no key → fastembed (multilingual MiniLM) on CPU


# ── Gemini ───────────────────────────────────────────────────────────────────
def _gemini_one(text: str, key: str, task: str) -> list[float]:
    body = json.dumps({"content": {"parts": [{"text": text}]}, "taskType": task}).encode()
    for attempt in range(5):
        try:
            req = urllib.request.Request(f"{GEMINI_URL}?key={key}", data=body,
                                         headers={"Content-Type": "application/json"})
            return json.loads(urllib.request.urlopen(req, timeout=60).read())["embedding"]["values"]
        except Exception:
            if attempt == 4:
                raise
            time.sleep(1.5 * (attempt + 1))
    return []


# ── local (fastembed) ────────────────────────────────────────────────────────
_LOCAL: dict = {}   # model_id → TextEmbedding (cached per model so query-time can
                    # use the SAME model the corpus was embedded with — see embed_query)


def _local_model(model_id: str | None = None):
    mid = model_id or LOCAL_MODEL
    if mid not in _LOCAL:
        from fastembed import TextEmbedding
        # GPU is opt-in (needs the `fbbackup[gpu]` extra → onnxruntime-gpu). The
        # setup wizard sets FBBACKUP_EMBED_DEVICE=gpu when it detects a GPU;
        # CUDA→CPU fallback is automatic if the GPU provider isn't available.
        if os.environ.get("FBBACKUP_EMBED_DEVICE", "").lower() == "gpu":
            _LOCAL[mid] = TextEmbedding(mid, providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
        else:
            _LOCAL[mid] = TextEmbedding(mid)
    return _LOCAL[mid]


def _local_embed(texts: list[str], is_query: bool, model: str | None = None) -> list[list[float]]:
    # jina-v3 / e5 / arctic are asymmetric; the query/passage prefixes matter.
    # Small batch by default: jina-v3's attention is memory-heavy — batch 256 OOMs
    # even a 24GB GPU. FBBACKUP_EMBED_BATCH tunes it (raise for lighter models).
    pfx = "query: " if is_query else "passage: "
    bs = int(os.environ.get("FBBACKUP_EMBED_BATCH", "16"))
    return [list(map(float, v)) for v in _local_model(model).embed([pfx + t for t in texts], batch_size=bs)]


# ── batched embedding + resumable checkpoint ─────────────────────────────────
# A whole-archive embed on a paced free key can take a long time; persist
# progress per batch so an interruption (browser close, 429 storm, power loss)
# resumes instead of re-embedding everything. The checkpoint is keyed to a
# fingerprint of (provider, model, row ids) so a changed corpus invalidates it.
def _embed_batch(provider: str, texts: list[str], key: str) -> list[list[float]]:
    if provider == "gemini":
        with ThreadPoolExecutor(max_workers=16) as ex:
            return list(ex.map(lambda t: _gemini_one(t, key, "RETRIEVAL_DOCUMENT"), texts))
    return _local_embed(texts, False)


def _fingerprint(provider: str, model: str, ids: list[str]) -> str:
    import hashlib
    h = hashlib.sha256(f"{provider}\0{model}\0{len(ids)}".encode())
    for i in ids:
        h.update(b"\0")
        h.update(i.encode())
    return h.hexdigest()[:16]


def _ckpt_paths(out_dir: Path) -> tuple[Path, Path]:
    return out_dir / "embed-ckpt.npy", out_dir / "embed-ckpt.json"


def _write_progress(out_dir: Path, done: int, total: int, provider: str, model: str) -> None:
    """Live progress for the in-app pill (read by /api/embed/status). Best-effort."""
    try:
        (out_dir / "embed-progress.json").write_text(json.dumps(
            {"done": done, "total": total, "provider": provider, "model": model,
             "ts": time.time()}), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def _clear_progress(out_dir: Path) -> None:
    try:
        (out_dir / "embed-progress.json").unlink(missing_ok=True)
    except Exception:  # noqa: BLE001
        pass


def _load_ckpt(out_dir: Path, fp: str) -> list[list[float]]:
    import numpy as np
    npy, js = _ckpt_paths(out_dir)
    try:
        meta = json.loads(js.read_text(encoding="utf-8"))
        if meta.get("fingerprint") == fp and npy.exists():
            return [list(map(float, v)) for v in np.load(npy)]
    except Exception:  # corrupt/mismatched checkpoint → start clean
        pass
    return []


def _save_ckpt(out_dir: Path, fp: str, vecs: list[list[float]], provider: str, model: str) -> None:
    import numpy as np
    npy, js = _ckpt_paths(out_dir)
    np.save(npy, np.asarray(vecs, dtype="float32"))
    js.write_text(json.dumps({"fingerprint": fp, "done": len(vecs),
                              "provider": provider, "model": model}), encoding="utf-8")


def _clear_ckpt(out_dir: Path) -> None:
    for p in _ckpt_paths(out_dir):
        try:
            p.unlink()
        except FileNotFoundError:
            pass


# ── unified API (used by the backend for the query, and embed() for the bulk) ─
def embed_query(text: str, provider: str | None = None, model: str | None = None) -> list[float]:
    provider = provider or resolve_provider()
    if provider == "gemini":  # keys resolved per provider
        return _gemini_one(text, gemini_key(), "RETRIEVAL_QUERY")
    return _local_embed([text], True, model)[0]   # query with the corpus's own model


def _content(text: str) -> str:
    """Clean substantive text for embedding: drop frontmatter, the H1 title, and
    image/link markup. Returns "" only for posts with NO real text, or for pure
    RESHARES whose text is just the boilerplate label (content == title and
    type == share) — those would pollute search. A single-line status/photo/link
    post has content == title too (the writer duplicates the text as title+body),
    but that text is REAL, so it IS embedded. (Earlier this dropped ~3k genuine
    short posts — see the type breakdown in the FB-distribution notes.)"""
    typ, body = "", text
    if body.startswith("---"):
        rest = body[3:].lstrip("\n")
        end = rest.find("\n---")
        if end != -1:
            m = re.search(r"^type:\s*(\S+)", rest[:end], re.M)
            typ = m.group(1) if m else ""
            body = rest[end + 4:].lstrip("\n")
    title, lines = "", []
    for line in body.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("# ") and not title:
            title = s[2:].strip()
            continue
        if s.startswith(("#", "![", "🔗", "[▶", "📍", "📘")):
            continue
        lines.append(s)
    content = " ".join(" ".join(lines).split())
    if not content:
        return ""
    if content == title and typ == "share":  # reshare boilerplate only
        return ""
    return content[:1500]


def embed(spaces_root: Path, out_dir: Path, workspace: str = "default") -> dict:
    import numpy as np

    provider = resolve_provider()
    key = gemini_key() if provider == "gemini" else ""
    if provider == "gemini" and not key:
        raise SystemExit(f"provider={provider} but no key")
    spaces_root = Path(spaces_root).expanduser()
    out_dir = Path(out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    base = spaces_root / workspace

    ids, texts = [], []
    for ydir in sorted(base.iterdir()):
        if not ydir.is_dir() or ydir.name.startswith("."):
            continue
        for p in sorted(ydir.glob("*.md")):
            txt = _content(p.read_text(encoding="utf-8", errors="replace"))
            if not txt:
                continue
            ids.append(f"{workspace}/{ydir.name}/{p.stem}")
            texts.append(txt)

    if not texts:
        print("no embeddable rows found (all rows are trivial/empty) — skipping "
              "embeddings; keyword search still works.", flush=True)
        return {"provider": provider, "count": 0, "dim": 0}

    model = GEMINI_MODEL if provider == "gemini" else LOCAL_MODEL
    batch = 256
    fp = _fingerprint(provider, model, ids)
    vecs = _load_ckpt(out_dir, fp)  # resume a prior run for THIS exact corpus
    start = len(vecs)
    if start:
        print(f"resuming embed at {start}/{len(texts)} via {provider} (checkpoint) …", flush=True)
    else:
        print(f"embedding {len(texts)} rows via {provider} ({model}) …", flush=True)
    _write_progress(out_dir, start, len(texts), provider, model)
    for i in range(start, len(texts), batch):
        vecs.extend(_embed_batch(provider, texts[i:i + batch], key))
        _save_ckpt(out_dir, fp, vecs, provider, model)  # checkpoint each batch
        done = min(i + batch, len(texts))
        _write_progress(out_dir, done, len(texts), provider, model)  # live pill
        print(f"  …{done}/{len(texts)}", flush=True)

    arr = np.asarray(vecs, dtype="float32")
    arr /= (np.linalg.norm(arr, axis=1, keepdims=True) + 1e-9)
    np.save(out_dir / "embeddings.npy", arr)
    (out_dir / "embed-ids.json").write_text(json.dumps(ids), encoding="utf-8")
    thr = local_threshold(model) if provider == "local" else THRESHOLDS.get(provider, 0.5)
    (out_dir / "embed-meta.json").write_text(json.dumps(
        {"provider": provider, "model": model, "dim": int(arr.shape[1]),
         "count": len(ids), "threshold": thr}), encoding="utf-8")
    _clear_ckpt(out_dir)  # done → drop the resume checkpoint
    _clear_progress(out_dir)  # done → embeddings.npy now signals "ready"
    print(f"saved {arr.shape} ({provider}) -> {out_dir / 'embeddings.npy'}", flush=True)
    return {"provider": provider, "count": len(ids), "dim": int(arr.shape[1])}


if __name__ == "__main__":
    embed(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("spaces-data"),
          Path(sys.argv[2]) if len(sys.argv) > 2 else Path("index"))
