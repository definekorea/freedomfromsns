# FreedomFromSNS — Deployment & Publishing (design + research)

How a **non-technical person** goes from *"I downloaded my Facebook data"* to
*"I'm browsing it — and (optionally) it's online for friends"* on **Windows,
macOS, or Linux**, with as few manual steps as possible. This is the plan that
realizes the North Star ("the easy way for anyone… on every major OS, even with
zero technical skill").

Status: **design + research doc.** Some of it already exists in `fbbackup`
(`ffs serve/share/export-static/publish/doctor`, `recommend_sharing()`, the
optional `local`/`gpu` extras, graceful ffmpeg/embedding fallbacks); the rest is
the roadmap. Each section marks ✅ done / 🔜 to build.

---

## 0. The ideal flow (what we're building toward)

```
download FB data ──► run one installer (picks language: English / 한국어)
   ──► it finds the data ──► processes (parse → build) ──► browser opens at
   localhost: YOUR ARCHIVE, LIVE — browse · filter · timeline · keyword search,
   with NO key, NO model download, NO wait
   ──► in-app, OPTIONAL "Smarter search?" — hardware-aware: a capable GPU/CPU →
       local embedding model (no key); otherwise → a free Gemini / Mistral key
   ──► in-app, OPTIONAL "Chat with your archive" — connect an AI (free or paid key)
   ──► (optional) "Publish online" → public URL (if chat is on: throttled + topic-locked)
```

One install command. No hand-installing Python, ffmpeg, or a venv. **The wow
moment — the user's real posts on screen — comes first and needs nothing.**
Everything AI is an *optional unlock* surfaced in-app, never a gate.

### 0.1 Feature tiers — the unlock ladder

Each tier is independently optional and **never blocks the tier below it**
(offline, no key, or a failed model download → the tier below still fully works).
The engine already supports this split — `embed.py:resolve_provider()` falls back
`gemini → weft → local`, browse/keyword-search touch no key or embeddings, and
`_semantic()` degrades to empty gracefully. What's new is the *packaging default*
(Tier 0 = pure wheels) and the *framing* (AI is a surfaced unlock, not step 2).

| Tier | Name (plain language) | Needs | Unlocks |
|---|---|---|---|
| **0** | **Your archive** | nothing — no key, no download, no questions | Browse · timeline/calendar · filter · **keyword search** · galleries · lightbox · link previews · video posters |
| **1** | **Smart search** | no key; an in-app opt-in. **Hardware-aware:** capable GPU/CPU → one-time local-model download (no key); weak hardware → a free Gemini / Mistral key | Meaning-based / semantic search |
| **2** | **Chat with your archive** | an AI connection (free Google key or your own) | RAG chat · agentic tool-loop · the "talk to your own posts" experience |

**Decision (locked):** Tier 1 is **opt-in**, not bundled — the basic install is
pure-Python wheels (tiny, instant), and "Smarter search?" is an in-app card that
either downloads the local model **or** connects a key. Keeps the default install
the smallest and most frictionless; semantic search is one click away.

---

## 1. Dependency reality — what's hard, and the substitutes

FFS is intentionally lean. Core is trivially portable; the only friction is three
**system-level** things. The rule: **everything hard is optional and degrades
gracefully, or has a pip-installable substitute.**

| Dependency | Role | Difficulty | Substitute / strategy | Status |
|---|---|---|---|---|
| Python 3.11+ | runtime | medium (don't make users install it) | **`uv`** installs + pins a managed Python; users never touch system Python | 🔜 |
| `fastapi` / `uvicorn` / `numpy` | the app | easy (pure wheels) | — | ✅ |
| **ffmpeg** | video poster-frame thumbnails | hard (system binary) | already optional (`shutil.which` → graceful skip). Substitute: **`imageio-ffmpeg`** (pip, bundles a static ffmpeg per-OS ~60 MB, `get_ffmpeg_exe()`); fall back to it when system ffmpeg is absent | partly ✅ → 🔜 |
| **fastembed / onnxruntime** | *local* offline embeddings | hard (large platform wheels) | already optional (`local` extra). Default = **Gemini embeddings** (a free key, no download). Only installed if the user picks "fully offline" | ✅ |
| `onnxruntime-gpu` | GPU embeddings | very hard (~277 MB, CUDA) | `gpu` extra, opt-in only when a CUDA GPU is detected | ✅ |
| **cloudflared** | publishing | easy-ish (single binary, no package mgr) | download the one binary for the OS on demand (the wizard/`ffs share` fetches it) | partly ✅ |

**Net:** a default install needs only pure-Python wheels. ffmpeg → pip substitute.
Local embeddings + GPU → opt-in. cloudflared → a single binary, only when publishing.

> **Strengthening the offline tier** (research): better small local embedding models
> (Nomic v1.5 / EmbeddingGemma / BGE-M3) and a **no-key local chat** option via tiny
> 4-bit/ternary models (Ollama GGUF; PrismML Ternary Bonsai 1.7B). See
> [`docs/local-models.md`](local-models.md). Not built yet.

### The `imageio-ffmpeg` substitution (🔜, small)

`spaces_backend._video_thumb` already checks `shutil.which("ffmpeg")`. Add a
resolver: prefer system ffmpeg, else `imageio_ffmpeg.get_ffmpeg_exe()` if the
package is present, else skip (video cards show a ▶ placeholder — already
handled). Add `imageio-ffmpeg` to a `media` extra so thumbnails "just work" on
native Windows/macOS without a system ffmpeg install.

---

## 2. Install matrix — native first, WSL + Docker as alternates

**Recommended everywhere: native via `uv`.** `uv` is one rust binary that
installs Python, makes the venv, and resolves deps — on all three OSes — so the
user never hand-installs Python or a venv.

### 2a. Native (all OSes) — the one-liner + wizard  🔜

A tiny bootstrap installs `uv`, then `uv tool install freedomfromsns` (or
`uvx freedomfromsns setup`), then launches the wizard.

- **Windows (native, no WSL):**
  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  uv tool install freedomfromsns
  ffs setup            # wizard: find data → connect AI → process → open browser
  ```
  A double-clickable `install-ffs.ps1` wraps this. ffmpeg via `imageio-ffmpeg`
  (no system install). cloudflared.exe downloaded on demand. **No WSL, no Docker
  required** — the North Star's "native Windows."
- **macOS / Linux:**
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  uv tool install freedomfromsns
  ffs setup
  ```
  A one-line `install-ffs.sh` wraps it.

### 2b. WSL (Windows power users)  ✅-ish

Already works (this repo runs in WSL). For users who prefer Linux tooling or
want an always-on box. The native path above is preferred for non-technical
users (no WSL setup). Document WSL as "advanced/alternate."

### 2c. Docker (always-on / servers)  🔜

A `Dockerfile` (python-slim + uv + ffmpeg apt + the app) and a `docker compose`
that mounts the FB export read-only and persists `index/` + `settings.json`.
For people who want it running 24/7 on a NAS/VPS and publishing permanently.

```yaml
# docker-compose.yml (sketch)
services:
  ffs:
    build: .
    volumes:
      - /path/to/facebook-export:/data/export:ro
      - ./ffs-state:/data/state         # index/, settings.json, .env
    environment: [ FBBACKUP_EXPORT_ROOT=/data/export, FBBACKUP_HOME=/data/state ]
    ports: ["8282:8282"]
```

---

## 3. Find the Facebook data automatically  🔜

The wizard should **not** ask the user to type a path. The export unzips to
`facebook-<name>-<date>-<hash>/` containing `your_facebook_activity/`.

**Auto-locate algorithm** (`ffs setup` / a `locate_export()` helper):
1. Candidate roots, per-OS:
   - Windows: `%USERPROFILE%\Downloads`, `\Desktop`, `\Documents`; also other drives' roots.
   - macOS/Linux: `~/Downloads`, `~/Desktop`, `~/Documents`.
2. In each, look for: a folder matching `facebook-*` **or** any folder containing
   `your_facebook_activity/posts/` (the load-bearing marker), **or** a
   `facebook-*.zip` / `*your*information*.zip`.
3. If a **.zip** is found, offer to unzip it (to `~/ffs/data/`).
4. If several candidates, show the newest with its date and let the user confirm.
5. Write the chosen path to `config.toml` `[export] root` (replacing the dev
   default `/mnt/d/dev/facebook-data`).

Cross-platform "Downloads" detection: `Path.home() / "Downloads"` covers the
common case; on Windows also read the `Shell Folders` registry value as a
fallback (localized/redirected Downloads).

---

## 4. The setup wizard (`ffs setup`)  🔜 (extends the existing `ffs doctor`)

Jargon-free, steers by intent (never "Mode A/B", never "cascade tier"). The
guiding rule: **get to the archive on screen with the fewest possible questions**,
then surface AI as optional unlocks (the §0.1 ladder) — don't gate the wow moment
on a key.

0. **Language** — first prompt (and only because it changes everything after):
   *English / 한국어*. Default from the OS locale (`LANG` / Windows UI language);
   the installer scripts, wizard prompts, and the app UI all honor it. (Bilingual
   KO+EN is a North Star commitment — see `principles.md`; today the UI is
   Korean-only, so this is a **gap to close**.)
1. **Find your data** — auto-locate (§3). If exactly one export is found, use it
   and **ask nothing**; only prompt if zero or ambiguous.
2. **Process (Tier 0)** — `parse → build` (fast, deterministic), then **open the
   browser immediately** at `http://127.0.0.1:8282`. The archive is now live:
   browse · filter · timeline · keyword search. **No key, no model, no wait.**
3. **Offer "Smarter search?" (Tier 1, optional)** — an in-app card, **hardware-aware**:
   - **Capable GPU** detected (CUDA, enough VRAM) → recommend the **local model**
     (`gpu` extra, no key); embeds in the **background** with a progress pill,
     never blocking browse.
   - **Capable CPU, no GPU** → offer the local model (`local` extra, CPU) **or** a
     free cloud key — let the user pick by patience vs. privacy.
   - **Weak hardware** → recommend a **free cloud key (Gemini / Mistral)** instead
     of a slow local embed.
   > Always labeled *optional* — keyword search already works. Embedding runs in
   > the background and is resumable; the archive stays fully usable throughout.
4. **Offer "Chat with your archive" (Tier 2, optional)** — a dismissible card:
   connect an AI (free Google key, or your own paid key) to chat with your posts.
   Never required; the card persists so it can be done later.
5. **Tour** — a first-run overlay points at Browse / Search / the ✦ AI unlocks /
   ⚙ Settings / and the **Publish** button.

`ffs doctor` (✅ exists) stays as the "what's wrong / what's missing" check the
wizard and support both lean on — including the **hardware probe** (GPU/VRAM,
CPU) that drives the Tier-1 recommendation, and the OS locale it reads for §0.

---

## 5. Publishing — going public with Cloudflare

Three levels, from "show a friend in 10 seconds" to "permanent site." FFS
already has `ffs share` (quick tunnel) and `ffs export-static` + `ffs publish`
(static hosts) + `recommend_sharing()`.

### Level 1 — Quick tunnel (instant, no account)  ✅ `ffs share`

```bash
ffs share          # cloudflared tunnel --url http://localhost:8282
```
Gives a random `https://<words>.trycloudflare.com` URL. **No login.** Caveats
(from Cloudflare): the URL **changes every restart**, it's capped at **200
in-flight requests**, and it's meant for testing, not production. Perfect for
"look at this now"; not for a URL you hand out.

### Level 2 — Permanent (free Cloudflare account + a domain)  🔜 the headline

A **named tunnel** gives a **stable URL that survives restarts**, unmetered
bandwidth, no open ports, no exposed IP — **free**. The one prerequisite:
**a domain whose DNS is on Cloudflare** (free plan). 

**Why make a permanent (free) Cloudflare account — the benefits:**
- **A stable, memorable URL** on *your* domain (`archive.yourname.com`) instead
  of a random string that dies on restart.
- **It stays up** — the named tunnel auto-reconnects; reboot-safe.
- **Free Zero-Trust Access** (up to 50 users): put a **login in front** of the
  whole archive (email one-time-code or Google), or keep the archive public and
  protect only an admin path. This is how you share with *specific* people.
- **Protection for free:** Cloudflare's CDN/cache, DDoS shielding, and basic
  analytics sit in front of your laptop; visitors never reach your IP.
- **No router/firewall config** — nothing to port-forward.

**Setup (the wizard will script this):**
```bash
cloudflared tunnel login                       # one browser login (the account)
cloudflared tunnel create ffs                  # creates a persistent tunnel
cloudflared tunnel route dns ffs archive.yourdomain.com
# config.yml: ingress → http://localhost:8282
cloudflared tunnel run ffs                      # (or install as a service)
```
Don't own a domain? Cheapest path: register one (a few $/yr) and add it to
Cloudflare's free plan — that's the only non-free part, and it's optional (Level
1 and Level 3 need no domain).

### Level 3 — Static publish (permanent, machine-off, no live chat)  ✅ `ffs publish`

```bash
ffs export-static --out site
ffs publish --target recommend          # picks github-pages / cloudflare-pages / …
```
A self-contained HTML/JS snapshot (browse + keyword search, **no AI**) on a free
static host. Permanent, your computer can be off. The trade-off: no semantic
search, no chat (those need the live server). `recommend_sharing()` already
picks the best host by archive size. **Cloudflare Pages** is the natural match.

> **Recommendation surfaced in-app:** the Publish button explains these three in
> plain language — *Quick link (now, temporary)* · *Permanent site with chat
> (free account + domain)* · *Permanent snapshot, no chat (free, always on)*.

---

## 6. Public AI chat — throttled + topic-locked  🔜

If the user exposes the **live** server (Level 2) with chat on, the public must
not be able to run up their AI bill or use it as a free general chatbot. A
**"public mode"** the shared instance runs in (`FFS_PUBLIC=1`, or a Settings
toggle written to `settings.json`):

- **Topic-lock** — a public system prompt clamp: *answer only from this archive
  and closely-related context; politely refuse anything off-topic.* (Prepended
  in `_chat`/`agent_chat`'s system prompt when public.) Optional allowlist of
  themes the owner sets.
- **Throttle** — per-IP rate limit (e.g. *N messages / minute / IP* + a daily
  cap), enforced in a middleware in front of `/api/chat`. A friendly "try again
  in a minute" message, not a 500.
- **Cost cap** — force the **fast** (cheap) lane, lower `maxOutputTokens`,
  **disable the agentic tool lane** publicly (it makes many calls), and disable
  expensive features. Optionally a global daily token budget that flips chat to
  "busy" when hit.
- **Read-only & private-safe** — public mode also hides erased/private posts
  (already excluded from export) and disables Settings / management endpoints.

Implementation hooks (small, all in `ffs_api`):
1. `PUBLIC = os.environ.get("FFS_PUBLIC") == "1"` (or settings flag).
2. `/api/chat`: if `PUBLIC` → ignore `agent`, force fast model, cap tokens,
   prepend the topic-lock clamp, run the request through the rate-limiter.
3. A tiny in-memory per-IP token bucket (no extra deps); the `taskqueue`-style
   pattern from Weft is the reference if we want bounded concurrency too.
4. Gate `/api/settings*`, `/api/privacy`, `/api/erase` behind "not public."

---

## 7. Build order (suggested)

Reordered around the §0.1 ladder: **ship Tier 0 the fastest, make AI an unlock.**

1. ✅ **`imageio-ffmpeg` fallback** + a `media` extra (frictionless video thumbs). (S) — done.
2. ✅ **`uv`-based installers** `install-ffs.{ps1,sh}` + `pyproject` console entry —
   default install is **pure wheels (Tier 0)**, no `local`/`gpu`/`media` extras. (M) — done.
   The viewer is now bundled **inside** the package (`fbbackup/viewer/`, shipped via
   package-data) so `uv tool install` is fully self-contained; state lives in a
   stable per-user `~/ffs/` (cwd-independent; FB data in `~/ffs/data/`). Verified end-to-end:
   wheel → isolated venv → serves the viewer + 24k-post index from any cwd.
3. ✅ **`ffs setup` wizard** (§4): installer **i18n** (§0 step 0, OS-locale default) +
   **auto-locate** the export (§3) + `parse → build` + **open browser at Tier 0**
   before any embedding. The wow moment, zero-key, fewest questions. (M) — done.
   *Distribution = **GitHub Releases**, not PyPI (less setup, no namespace): the
   installer resolves the latest release's wheel via the GitHub API and `uv tool
   install`s it straight from the HTTPS asset URL — no git, no clone, no PyPI. The
   end-user one-liner is `curl …/install-ffs.sh | sh` (or the `.ps1` via `irm | iex`).
   Remaining for "any newcomer": the repo must be **public**, and each version cut
   as a release: `uv build --wheel && gh release create vX.Y.Z dist/*.whl`.*
4. ✅ **Hardware probe + Tier-1 setup** — `ffs setup` probes the GPU (nvidia-smi) /
   Apple-Silicon / CPU after build and offers **smart search**: `[1]` local model
   (auto-installs `fastembed`/`onnxruntime-gpu` via uv on demand), `[2]` a Gemini
   API key, `[3]` skip. The chosen provider embeds in a **detached background
   process** (logs to `embed.log`) while the archive opens — Tier 0 never waits.
   `--embed local|gemini|skip` for non-interactive runs. (M) — done.
5. **Mistral embedding provider** in `embed.py` (alongside gemini/weft/local) so the
   weak-hardware route offers Gemini **or** Mistral. (S)
6. **Background, resumable embedding** surfaced as an in-app progress pill, so Tier 1
   never blocks browse. (S–M; `embed` is already resumable.)
7. **"Chat with your archive" (Tier 2)** unlock card + **Public mode** for the chat
   (throttle + topic-lock + cost cap) (§6). (M)
8. ✅ **Publish button** in the UI (🌐) — warns to privatise sensitive posts and
   that reshares are mostly missing, then starts a **Cloudflare quick tunnel**
   (`/api/publish/start|stop|status`, loopback-only, isolated config home) and
   shows the temporary URL with copy + stop. (M) — done. *(First-run tour still TODO.)*
9. ✅ **Named-tunnel helper** — `ffs tunnel <hostname>`: guided, bilingual. Automates
   the scriptable Level-2 steps (`tunnel create` → `route dns` → write a **dedicated**
   `~/ffs/cloudflared.yml` → run) and guides the parts that can't be scripted (the
   one-time `cloudflared tunnel login` + registering a free Cloudflare account/domain).
   `--dry-run` prints the plan; `--run` starts it; suggests `service install` for
   always-on. Never touches an existing `~/.cloudflared/config.yml`. (M) — done.
10. **Dockerfile + compose** for always-on. (S)
11. ✅ **Hardware tester v2** — `ffs setup` now: static probe (cores, **available** RAM,
    `onnxruntime.get_available_providers()`, GPU/Apple) → curated `EMBED_MODELS` registry
    pick (`mini`/`large`) → **micro-benchmark in a subprocess** on a real sample → projects
    the full-archive time + RAM and **backs off to a cloud key** when it'd be too slow or
    OOM-risky (the live embed is resumable). Default flipped to MiniLM-multilingual; long-
    context/1024-dim models ruled out for CPU. Measured data in [`local-models.md`](local-models.md). (M) — done.
    *(Live-embed watchdog — switch mid-run if it stalls — is the remaining nice-to-have.)*
12. **Mobile** — see the Mobile section below. (L)

---

## 8. Mobile (future)

Two distinct goals; treat them separately.

### 8a. Mobile **browsing** (near-term) 🔜
The published archive (and the local server on a phone's browser) should be fully usable
on a small screen. Work:
- **Mobile UI/UX audit** of the viewer — responsive grid/calendar, touch targets, the
  lightbox + thumb-strip scrubber and the chat panel on narrow screens, safe-area insets.
- Make the viewer an installable **PWA** (manifest + service worker for an offline shell),
  so a published archive can be "added to home screen." Browsing is static-friendly, so
  this pairs naturally with `ffs export-static` + the Publish flow.

### 8b. On-device **hosting + processing** (ambitious, long-term) 🔭
Running parse → build → embed → serve *on the phone itself*, not just browsing. The
small-model findings make pieces of this plausible:
- **Embeddings on-device:** the winning CPU model (`paraphrase-multilingual-MiniLM-L12-v2`,
  86 texts/s, 0.75 GB) is mobile-sized; run via **onnxruntime-mobile / CoreML / NNAPI**.
- **Chat on-device:** ternary/4-bit models already run on phones (PrismML **Ternary Bonsai**
  ~27 tok/s on an iPhone 17 Pro Max; see [`local-models.md`](local-models.md)) via
  llama.cpp / MLC / a BitNet runtime.
- **The hard part is the stack, not the models:** FastAPI/uvicorn + the Python pipeline
  don't run natively on iOS/Android. Realistic paths, cheapest first: (1) **run the server
  on a home machine, browse on mobile** (already works via Publish); (2) **Android via
  Termux** running the existing app; (3) a **native/React-Native shell + embedded ONNX/LLM
  runtimes** for a true on-device app (large effort — its own project).
- Sequencing: (1) the mobile UI/UX audit + PWA for browsing → (2) research on-device
  runtimes → (3) on-device processing. The **hardware tester** (item 11) is the gate that
  decides what a given phone can actually do.

---

## Sources
- uv (Astral): <https://docs.astral.sh/uv/getting-started/installation/>, scripts <https://docs.astral.sh/uv/guides/scripts/>
- Cloudflare Tunnel — quick vs named, domain requirement, limits:
  <https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/>,
  <https://developers.cloudflare.com/cloudflare-one/faq/cloudflare-tunnels-faq/>
- imageio-ffmpeg (bundled static ffmpeg): <https://github.com/imageio/imageio-ffmpeg>, <https://pypi.org/project/imageio-ffmpeg/>
- Cloudflare Access (Zero Trust, free tier) for gating the public site.
- Mistral embeddings (`mistral-embed`) — cloud route for the weak-hardware Tier-1 option: <https://docs.mistral.ai/capabilities/embeddings/>
