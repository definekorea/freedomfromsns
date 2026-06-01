# FreedomFromSNS

Browse, search, and **chat with your Facebook archive** — entirely on your own
machine. Point it at a Facebook "Download Your Information" (JSON) export and it
becomes a fast, private, searchable timeline with an AI that can actually open
your posts and show you the photos in them.

- **Local-first & private** — your export is read-only and never leaves your
  machine. No cloud middleman.
- **Gemini-only** — one API key powers both the semantic index and the chat
  (embeddings: `gemini-embedding-001`; chat: `gemini-2.5-flash` / `-3.1-pro`,
  selectable in the UI).
- **Agentic chat** — the AI uses tools (`search_archive`, `get_post`,
  `get_link_preview`) to explore your archive and answer with the *real* photos,
  links, and text from your own posts — grounded, no hallucinated URLs.
- **Rich browsing** — grid + calendar views, instant keyword + semantic search,
  a full-screen image lightbox.

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
