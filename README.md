# FreedomFromSNS

Browse, search, and **chat with your Facebook archive** — entirely on your own
machine, fast and private. Point it at a Facebook "Download Your Information"
(JSON) export and it becomes a searchable timeline of **your own posts**, with an
AI that opens them and shows you the photos.

Built on four principles — **simplicity, speed, convenience, and a focus on your
own postings** (your photos / videos / writing, not the reshares you forwarded).
See [`docs/principles.md`](docs/principles.md).

- **Your content first** — the default feed is what *you* posted. Reshares (whose
  originals Facebook strips from the export and can't be linked back) and
  content-less posts are tucked into click-into buckets (공유 · 링크 · 미분류),
  not the main timeline.
- **Fast & local** — browse/calendar/search render client-side; image + video
  thumbnails and link previews are cached; nothing leaves your machine and the
  export is read-only.
- **Gemini-only** — one API key powers both the semantic index and the chat
  (embeddings: `gemini-embedding-001`; chat: `gemini-2.5-flash` / `-3.1-pro`,
  selectable in the UI).
- **AI chat, first-class** — a grounded RAG or an agentic Gemini tool-loop
  (`search_archive`, `get_post`, `get_link_preview`) that answers from the *real*
  photos, links, and text in your own posts — no hallucinated URLs.
- **Rich browsing** — grid + calendar, instant keyword + semantic search, link
  previews, video posters, a full-screen image lightbox with a position scrubber.

## Setup

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e .
echo "GEMINI_PAID_API_KEY=your-key-here" > .env   # one key, that's it
```

Edit `config.toml` → `[export].root` to point at your unzipped export
(forward slashes, e.g. `D:/dev/facebook-data`).

## Use

```bash
ffs parse     # export JSON → index/posts.jsonl
ffs build     # → spaces-data/<year>/*.md
ffs embed     # → index/embeddings.npy   (Gemini; resumable)
ffs serve     # → http://localhost:8282
#   ffs index    runs parse + build + embed in one go
#   ffs status   shows what's present
```

Open **http://localhost:8282**.

## How it works

```
Facebook JSON export (read-only)
      │  ffs parse / build / embed
      ▼
index/ (posts.jsonl, embeddings.npy)  +  spaces-data/<year>/*.md
      │
      ▼
ffs serve  →  one FastAPI process on :8282
   ├─ /api/index   browse snapshot (client renders grid/calendar)
   ├─ /api/search  keyword + Gemini-semantic
   ├─ /api/chat    RAG (fast) OR agentic tool-loop (🔧 도구)
   └─ /api/fb/*    media serve, post detail, link unfurl
            └─ Gemini paid API  (embeddings offline; chat online)
```

Public sharing (Cloudflare tunnel) and a one-click installer are planned.
