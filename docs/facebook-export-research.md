# Facebook Data Export — Format, Tools & Recovery Research

Reference notes for FreedomFromSNS development. Compiled 2026-06-01 from web
research across the Facebook "Download Your Information" (DYI) format, the
open-source tool ecosystem, and the reshare/permalink-recovery problem.

> **One-line takeaways**
> - Parse **JSON**, never HTML. Always apply the **latin1→utf8 mojibake fix** (Meta never fixed it).
> - There is **no official schema**; the format drifts silently — parse defensively.
> - `pfbid` is **rotating and irreversible** — extract the stable numeric `fbid` instead (we do).
> - ~7k content-less reshares are **genuinely unrecoverable** from the export; only logged-in scraping recovers them.
> - The maintained, local-first, **FB-specialized browser + free/offline semantic search** niche is **empty** — that's our lane.

---

## 1. Export format

### 1.1 JSON vs HTML

Facebook offers both formats for the whole download. **Parse JSON.**

| | HTML | JSON |
|---|---|---|
| Purpose | Human browsing (`start_here.html`) | Machine parsing |
| Schema | None — presentation markup, scrape-only | Community-documented structure |
| Encoding | Renders correctly (normal UTF-8 page) | **Mojibake bug** (§1.2) — must be fixed |
| Recommendation | Read-once in a browser | Archiving / analysis / our tool |

Modern download path (2024+): **Settings & privacy → Accounts Center → Your
information and permissions → Download your information → Download a copy**
(not "Transfer a copy", which is the GDPR/DTP direct-transfer path). Options:
format (HTML/JSON), media quality (High/Med/Low), date range. Export is
asynchronous — Facebook emails a link, often up to ~24h later.

### 1.2 The mojibake / encoding bug (still present, never fixed)

Facebook's JSON serializer emits UTF-8 **bytes** wrongly escaped as `\u00XX`
sequences — it conflated "UTF-8 byte" with "Unicode escape". After a normal
JSON parse, every non-ASCII character appears as a run of latin1/C1 chars
(U+0080–U+00FF), so Korean/emoji/accented text is garbled.

**Worked example:** `ř` (U+0159) → UTF-8 bytes `c5 99` → exported as
`Å`. **Canonical fix** (apply recursively to every string value):

```python
fixed = text.encode("latin1").decode("utf8")
```

`.encode("latin1")` recovers the raw bytes; `.decode("utf8")` reads them
correctly. Guard it (already-correct strings raise on `.encode("latin1")` →
try/except, leave untouched). FreedomFromSNS does this in `fbbackup/mojibake.py`.

Confirmed **still present in 2025-2026 exports** (no evidence Meta ever fixed
it). The **HTML export is NOT affected** (it's a normal UTF-8 page) — a point
in HTML's favor for *display*, but JSON still wins for *parsing*.

### 1.3 Directory / file structure (modern, 2023+)

Everything nests under **`your_facebook_activity/`** (older exports used a flat
`posts/`). Media lives under `your_facebook_activity/posts/media/<bucket>/`.
Posts are chunked across `your_posts__check_ins__photos_and_videos_*.json`
(numeric suffixes when large).

Files in/around `posts/`:

| File | Contents | We use it? |
|---|---|---|
| `your_posts__check_ins__photos_and_videos_*.json` | Main timeline posts array | ✅ |
| `content_sharing_links_you_have_created.json` | Share/deep links you generated, each with a `fbid` + the original URL | ✅ (links + fbid) |
| `edits_you_made_to_posts.json` | Edit history; each entry carries the post's `fbid` (127 MB in our test export) | ✅ (fbid index) |
| `your_uncategorized_photos.json` | Photos not in any album, as media objects | ❌ **gap** |
| `your_videos.json` | Uploaded videos as media objects | ❌ **gap** |
| `album/` (dir, one JSON per album) | Album name/description/cover + `photos[]` | ❌ **gap** |
| `archive.json` | Legacy consolidated activity snapshot | ❌ |
| `places_you_have_been_tagged_in.json` | Check-in tags | ❌ |

Media binaries are stored at `posts/media/<album-or-bucket>/<id>.jpg|mp4`; each
JSON `media` entry's `uri` is a **path relative to the export root** (resolve
against the export root, not the JSON file).

### 1.4 Canonical post JSON schema

```jsonc
{
  "timestamp": 1480178054,                  // Unix epoch SECONDS, UTC
  "title": "Jane Doe updated her status.",  // FB-generated narration (types the post)
  "data": [ { "post": "the status text" } ],// post body; may be absent (media-only)
  "attachments": [ { "data": [
    // heterogeneous — each element is ONE of (switch on the key):
    { "media": {
        "uri": "your_facebook_activity/posts/media/.../img.jpg", // relative to export root
        "creation_timestamp": 1480178054,
        "title": "...", "description": "...",                    // optional caption
        "media_metadata": { "photo_metadata": { "exif_data": [ {
            "iso": 400, "camera_make": "Canon", "latitude": ...,
            "longitude": ..., "taken_timestamp": ..., "upload_ip": "..." } ] } }
    } },
    { "external_context": {                  // a shared link
        "url": "https://example.com/article",
        "name": "title / original caption",  // optional — often the reshared content text
        "source": "Instagram"                // optional — the platform/domain
    } },
    { "text": "..." },                       // extra structured attachment text (e.g. memories)
    { "place": { "name": "Cafe XYZ",
                 "coordinate": { "latitude": ..., "longitude": ... },
                 "address": "...", "url": "..." } }
  ] } ]
}
```

Implementer notes:
- `timestamp` is **seconds**, not ms.
- `data[]` and `attachments[].data[]` are arrays; iterate. The attachment array
  is **heterogeneous** — the single key (`media`/`external_context`/`text`/
  `place`) is the discriminant.
- `external_context.name` frequently holds the **reshared original's text** and
  `source` the platform (Instagram/YouTube) — capture both (we do).
- `media.media_metadata.photo_metadata.exif_data` is a **list** of EXIF objects
  (camera, GPS, `upload_ip`).
- Handle both a bare-array root and a single-key wrapper-object root; glob files
  by prefix; tolerate missing keys (silent format drift).

---

## 2. Open-source ecosystem & competitive landscape

The space splits into **Messenger-only** tools (crowded, mature) and
**whole-export** tools (posts/photos/timeline — thin). **AI/semantic/RAG over a
personal FB archive is essentially a green field.**

### 2.1 Closest competitors (whole-export / AI)

| Project | Lang | Stars | Status | Notes |
|---|---|---|---|---|
| [facebookresearch/personal-timeline](https://github.com/facebookresearch/personal-timeline) | Py+React | ~371 | **Archived Nov 2025** | The closest prior art: ingest FB posts → SQLite, React browse UI, timeline/map, **RAG Q&A** (OpenAI). Research-grade, now dead, cloud-only. |
| [timelinize/timelinize](https://github.com/timelinize/timelinize) | Go+JS | ~3.5k | Active | Heavyweight multi-source self-hosted timeline (FB = one of many). Browse, gallery, map, search. FB fidelity shallow; "unstable, schema changing." |
| [Lackoftactics/facebook_data_analyzer](https://github.com/Lackoftactics/facebook_data_analyzer) | Ruby | ~543 | Archived 2024 | The de-facto "FB wrapped" — friend rankings, vocab, temporal patterns → Excel/HTML. Analytics, not browsing. |
| [Feedsake](https://feedsake.com/) | web (closed) | — | Live | Product competitor: FB/IG export → quiet chronological feed, in-browser, by year/friend/place/words. UX prior art. |

### 2.2 Messenger-only (representative, not exhaustive)

`ownaginatious/fbchat-archive-parser` (classic parser, archived), 
`simonwongwong/Facebook-Messenger-Statistics` (stats), 
`DuckCIT/Facebook-Messenger-JSON-Viewer` + `Yukaii/messenger-JSON-viewer`
(polished in-browser viewers), `karlicoss/fbmessengerexport` (→ SQLite, part of
the HPI personal-data ecosystem), `Cretezy/fddp` (modern message processor).

### 2.3 Whole-export parsers / analytics (smaller)

`numbersprotocol/fb-json2table`, `SamuelePilleri/facebook-schemas` (JSON
Schemas — closest thing to a spec), `addshore/facebook-data-image-exif` (EXIF
re-injection), `hshore29/FacebookActivityGrapher`, `sbaack/FacebookQuantifier`,
`ferran7e/facebook-parser`, `spencerhance/fb-data-parser`.

### 2.4 Gaps no tool fills (FreedomFromSNS's opening)

1. **A maintained whole-export browser** — the one research attempt is archived; Timelinize is multi-source/shallow. **Open.**
2. **Local-first, free/offline semantic search / RAG over FB posts** — only `personal-timeline` did it (dead, cloud-only). **Open.**
3. **Zero-skill, cross-OS one-click install** — everything else needs a dev environment. **Open.**
4. **Encoding correctness as a solved default** — re-solved from scratch in every parser; no shared FB decoder.
5. **Unified searchable photo/video gallery + posts + (later) messages** in one timeline.
6. **Resilience to schema drift** — most tools died because the format moved and no one maintained them.

> **Positioning:** whole-export local viewer **+** free/offline semantic search
> **+** non-technical one-click install **+** FB-specialized — not served by any
> maintained OSS project today.

---

## 3. Reshares, IDs & permalink recovery

**Theme:** since 2022 Meta has deliberately broken id-based access. Official
recovery of your own old reshared content is effectively dead; the export
strips reshared originals.

### 3.1 Constructing permalinks from a numeric `fbid`

| Form | Status (2025-2026) |
|---|---|
| `facebook.com/<fbid>` / `fb.com/<fbid>` | Resolves via redirect **when logged in**. Simplest. (What we emit.) |
| `facebook.com/permalink.php?story_fbid=<fbid>&id=<userid>` | Live, but needs the owner's numeric `id` too; FB now often puts a `pfbid` in the `story_fbid` slot. |
| `facebook.com/<username>/posts/<fbid>` | Works with a known vanity, but FB increasingly serves the `…/posts/pfbid…` form. |
| Photo: `facebook.com/photo.php?fbid=<id>` | Works **logged in**, if still visible. |

**Caveat:** all are **login-gated** — they're "open in Facebook" links, not
anonymous deep links. Fine for the archive owner; a logged-out shared viewer
hits a wall.

### 3.2 Where the `fbid` lives in the export

There is **no clean per-post id field** in the DYI `your_posts` JSON. Numeric
fbids surface only incidentally in:
- `edits_you_made_to_posts.json` (edited posts) — keyed by timestamp; carries `fbid`.
- `content_sharing_links_you_have_created.json` (links you made) — `fbid` + original URL.
- Media filenames / album ids — these are **media-object** ids, not the parent post's id.

FreedomFromSNS builds a `timestamp → fbid` **and** `text-prefix → fbid` index
from the first two (edit timestamps differ from post times, so text catches
what timestamp misses). Coverage on our test export: **4,622 / 20,938 posts
(1,474 of the reshares)**. The rest were never edited → no fbid anywhere.

### 3.3 `pfbid` — opaque, rotating, irreversible

[Meta (Sep 2022)](https://about.fb.com/news/2022/09/deterring-scraping-by-protecting-facebook-identifiers/):
`pfbid` ("Pseudonymized Facebook Identifier") combines a **timestamp + the FBID
into a time-rotating id** to deter scraping, while keeping links alive.
Consequences:
- The same post gets **multiple pfbids over time** → never use a pfbid as a dedup key.
- It **cannot be reversed** locally to the numeric id (only an embedded timestamp is extractable; the FBID portion is encrypted).
- **Rule:** treat `pfbid` as opaque; if you need a stable id, resolve it once out-of-band (§3.4) and store the numeric result.

### 3.4 Recovering reshared / original content (ranked by what works)

1. **`facebook.com/plugins/post.php?href=<url-encoded-post-url>`** — the embed
   endpoint returns a still-public post's canonical numeric id + rendered
   content **without login or scraping**. The single most reproducible recovery
   path. ⚠ Loads Facebook's iframe/tracking → conflicts with privacy-by-
   construction; keep **optional**. Can't resurrect deleted/private originals.
2. **Activity Log** (your own account) — links back to originals; manual, not bulk.
3. **Logged-in timeline scraping** (own session) — Tampermonkey walkers
   ([`nemecec/scrape-facebook-timeline`](https://github.com/nemecec/scrape-facebook-timeline)),
   the ESuit Chrome extension, etc. Captures the full rendered post incl. the
   reshared original the export stripped. **Fragile** (breaks on DOM changes)
   but the **only robust way to fill the ~7k content-less reshares.** This is
   what fbbackup's own extension does.
4. **Graph API** — effectively dead for this: `user_posts` needs App Review,
   returns only your-timeline posts, **omits videos**, and never returns
   reshared originals.
5. **Third-party scrapers** ([`kevinzg/facebook-scraper`](https://github.com/kevinzg/facebook-scraper), Apify) — **public posts only.**

### 3.5 Media id → URL

A photo fbid → `facebook.com/photo.php?fbid=<id>` (logged in, if still visible).
The export's **local media files are the authoritative copy**; a constructed
URL is just a "view on Facebook" link. Video URL construction is unreliable.

---

## 4. Actionable implications for FreedomFromSNS

| Finding | Action | Priority |
|---|---|---|
| `your_uncategorized_photos.json` / `your_videos.json` / `album/` unparsed | Ingest for a more complete gallery | Medium |
| ~7k reshares unrecoverable from export | Wire up fbbackup's **live-scan extension** as the only real fill | High (if completeness matters) |
| `fbid` permalinks are login-gated | Keep the "Facebook에서 보기" link; document the logged-out caveat | Done |
| `pfbid` irreversible | Keep extracting numeric `fbid`; never use pfbid as a key | Done |
| `plugins/post.php` recovery | Optional, privacy-gated toggle for reshares with a URL | Low |
| Niche is open (personal-timeline archived) | Lean into local-first + free/offline semantic + one-click install | Strategic |
| Format drifts silently | Keep defensive parsing; validate against `facebook-schemas` | Ongoing |

---

## 5. Key sources

**Format & encoding**
- [krvtz — How Facebook got Unicode wrong](https://krvtz.net/posts/how-facebook-got-unicode-wrong.html)
- [multun gist — the latin1→utf8 fix](https://gist.github.com/multun/f487fc648de893c136298a8491ad5f16)
- [sorashi.dev — fix FB JSON archive encoding](https://sorashi.dev/fix-facebook-json-archive-encoding/)
- [SamuelePilleri/facebook-schemas](https://github.com/SamuelePilleri/facebook-schemas) · [numbersprotocol/fb-json2table](https://github.com/numbersprotocol/fb-json2table)
- [addshore — FB image EXIF structure](https://addshore.com/2019/02/add-exif-data-back-to-facebook-images-0-1/)

**Tools / landscape**
- [facebookresearch/personal-timeline](https://github.com/facebookresearch/personal-timeline) · [timelinize](https://github.com/timelinize/timelinize) · [Lackoftactics/facebook_data_analyzer](https://github.com/Lackoftactics/facebook_data_analyzer) · [Feedsake](https://feedsake.com/)

**IDs / reshare recovery**
- [Meta — Deterring scraping by protecting Facebook identifiers (pfbid)](https://about.fb.com/news/2022/09/deterring-scraping-by-protecting-facebook-identifiers/)
- [nayuki — Understanding Facebook IDs](https://www.nayuki.io/page/understanding-facebook-ids)
- [t-wy gist — canonical Post ID without pfbid](https://gist.github.com/t-wy/66faed8679d127793891ecb775efdaa9)
- [HN — new Facebook URLs / post.php trick](https://news.ycombinator.com/item?id=32117489)
- [nemecec/scrape-facebook-timeline](https://github.com/nemecec/scrape-facebook-timeline) · [kevinzg/facebook-scraper](https://github.com/kevinzg/facebook-scraper)

> **Caveat:** there is no authoritative public doc of the *current* DYI
> `your_posts` schema — most online examples are the **Graph API** shape, which
> differs. Always validate against a real export ZIP (we did).
