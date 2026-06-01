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

## Install

One command — it installs a managed Python via [`uv`](https://docs.astral.sh/uv/),
then FreedomFromSNS (from the latest GitHub Release — no PyPI, no git, nothing to
compile), then launches the wizard. You only need this command + your Facebook
download; an API key is optional.

**Windows** (native — no WSL, no Docker):
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/definekorea/freedomfromsns/master/install-ffs.ps1 | iex"
```

**macOS / Linux:**
```bash
curl -fsSL https://raw.githubusercontent.com/definekorea/freedomfromsns/master/install-ffs.sh | sh
```

State (config, index, archive) lives in `~/FreedomFromSNS/`. The wizard
auto-locates your export, so there's nothing to configure by hand.

### From source (development)
```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e .
ffs setup          # or edit config.toml → [export].root yourself
```

## Use

The easy path — one command, English or 한국어, no AI key needed:

```bash
ffs setup     # find your export → build → open the browser at Tier 0
```

It auto-locates your Facebook download, parses + builds your timeline, and opens
it at `http://localhost:8282`. **Browse, filter, and keyword search work
immediately, with no API key.** Semantic search and AI chat are optional unlocks
offered in-app (a one-time local model download, or a free key).

Or run the steps by hand:

```bash
ffs parse     # export JSON → index/posts.jsonl
ffs build     # → spaces-data/<year>/*.md
ffs embed     # → index/embeddings.npy   (semantic search; resumable)
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
