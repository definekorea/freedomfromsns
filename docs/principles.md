# FreedomFromSNS — Principles

FreedomFromSNS has **four core principles**. Everything else — including which
Weft ideas we keep or drop (further below) — exists to serve them.

## Core principles

1. **Simplicity.** One local process, one provider (Gemini), one-step actions.
   No jargon, no provider/tier vocabulary, no configuration mazes. Complexity is
   *ours* to hide (a single FastAPI server, venv/`uv`-managed Python, prebuilt
   assets), never the user's to manage. When something can be simpler, make it
   simpler. (We deliberately collapsed Weft's 4-layer chat proxy into one local
   process — keep it that lean.)

2. **Speed.** The archive must feel *instant* even at 20k+ posts. Browse, filter,
   and calendar render client-side from a precomputed snapshot; retrieval is a
   deterministic embed + cosine kNN (only the synthesis is an LLM call);
   thumbnails (image + ffmpeg video posters) and link previews are cached on
   disk; the lightbox windows its thumbnail strip so thousands of items never
   stall. Pre-warm and cache the slow parts.

3. **Convenience.** Point at an export and go. Sensible defaults, graceful
   fallbacks, honest "this needs X" messages (`ffs doctor`). The things you want
   are surfaced; the noise is hidden by default. One-click navigation (open a
   post, scrub a gallery, jump to a year) beats any CLI step.

4. **Focus on your OWN postings — not reshares.** The default feed (전체) is the
   content *you* made: your photos, videos, and writing. Reshares of other
   people's posts — whose originals Facebook strips from the export, and which
   can't be linked back (the post id only resolves via an uncomputable, encrypted
   `pfbid`) — are de-emphasized into a click-into **공유** bucket, never the main
   timeline. Links and loose media get their own click-into buckets too
   (**링크**, **미분류**); empty/content-less posts are hidden entirely. We
   optimize for the signal (your life), not the noise (what you forwarded).

And the **AI chat is a first-class feature**, not a bolt-on: chat with your
archive (grounded RAG, or an agentic Gemini tool-loop) so it answers from your
*real* posts and shows your *actual* photos — the most direct expression of
principle 4. Related features (semantic search, the gallery lightbox, link
previews) all serve the same end: getting *you* to *your* content, fast.

These four are the lens. The sections below map which of [Weft](https://github.com/unattachedgray/Weft)'s
broader ideas support them and which we drop — FreedomFromSNS began as the
standalone embodiment of Weft's Facebook "North Star," but it's a far simpler
project, so most of Weft's agent-framework machinery doesn't apply.

---

## 1. The North Star — the mission behind the principles

Weft's flagship goal, stated for the Facebook build, *is* FreedomFromSNS:

> **Be _the_ easy way for anyone to keep and browse their Facebook archive — on
> every major OS, even with zero technical skill.**

"Easy" is the spec, not a nicety. Concrete commitments (and where we stand):

| Commitment | Status in FreedomFromSNS |
|---|---|
| **One step to install, every OS** (no hand-installing Bun/venv/compilers) | ❌ today it's `git clone` + venv + `pip install`. **Gap.** |
| **Guided, jargon-free onboarding** ("connect any AI → point at your export → done"; never "Mode A/tier") | ⚠ partial — `ffs doctor` triages, but no first-run wizard. **Gap.** |
| **Works with whatever they have** (free key, paid key; sensible fallbacks; honest "needs X" messages) | ⚠ Gemini-paid-only by choice; `doctor` gives honest messages. Could add a free-tier fallback. |
| **Private by construction** (runs on their machine; export read-only & never modified; sharing explicit + revocable) | ✅ local, read-only export, no telemetry. (Sharing not built yet.) |
| **Bilingual (KO + EN), more later** | ❌ UI is Korean-only. **Gap** — the owner is bilingual and the data is mixed. |
| **It just keeps working** (watchdogs, resumable jobs, graceful degradation) | ⚠ resumable embed ✅; no watchdog (it's launch-on-demand, not always-on). |

**The three open gaps — install, onboarding, bilingual — are the highest-value
next work**, because they're what stands between "works for Julian" and "works
for anyone." Everything else is polish on top.

## 2. The four coding guidelines — adopt **whole**

From Weft's user-scope rules; universal:
1. **Think before coding** — state assumptions, surface tradeoffs, ask when unclear.
2. **Simplicity first** — minimum code that solves it; no speculative abstraction. *(FreedomFromSNS deliberately collapsed Weft's 4-layer chat proxy into one local process. Keep it that lean.)*
3. **Surgical changes** — touch only what the task needs; match surrounding style.
4. **Goal-driven execution** — turn the task into a verifiable goal; verify in a real browser (we do, via Playwright).

## 3. Deterministic over LLM — adopt **whole**

A parser/regex/substitution beats a `claude -p` for anything reproducible.
Already load-bearing here:
- Retrieval is deterministic (Gemini embed + cosine kNN), only the synthesis is an LLM call.
- The agent's images are grounded by **deterministic ref→URL substitution** — the model emits `[[img1]]`, never a URL, so it *cannot* hallucinate one.
- fbid permalinks, album tags, media extraction — all deterministic from the export.

## 4. Privacy by construction — adopt **whole**

Everything runs on the user's machine; the export is treated as **read-only and
never written**; any future sharing must be **explicit, read-only, revocable**.
Note the honest caveat (from the research): `facebook.com/<fbid>` links are
login-gated — fine for the owner, a wall for a logged-out shared viewer. The
unfurl path deliberately **skips facebook.com** (no FB tracking iframe).

## 5. Free / cheapest-capable first — adopt **in part**

Weft's rule is "stay free; reach for the cheapest capable option." We currently
run **Gemini paid only**, by the owner's explicit choice ("gemini only, keep it
simple"). The North Star's "works with whatever they have" implies a future
**free-tier fallback** (Gemini free key, or fully-offline local embeddings via
fbbackup's `local` provider) for users without a paid key — already supported in
`embed.py`, just not wired into the wizard.

## 6. The Flywheel — adopt **honestly** (mostly a plain tool)

Weft's central principle is to engineer self-reinforcing loops. **FreedomFromSNS
is, honestly, a plain tool** — a browser over a static export — and per Weft's
own Flywheel Audit fallback, that's fine: *"still adopt if genuinely useful…  as
a plain tool, honestly labelled. Don't fake a loop."* Don't force a flywheel
where there isn't one.

The few genuine loop angles, if ever pursued (each needs a governor):
- **Live-scan enrichment** — the browser extension re-walks the profile and
  feeds new/reshared content back into the archive (the one real way to recover
  the ~7k content-less reshares). Capture → index → browse → scan-again.
- **Chat → follow-ups** — each answer could surface 2-3 grounded next questions
  (close the loop cheaply). Light, optional.

## 7. Reliability — adopt **in part**

"It just keeps working" matters, but FreedomFromSNS is **launch-on-demand**, not
an always-on supervised stack, so Weft's watchdog/pm2 apparatus is overkill.
What we took: **`ffs doctor`** (Weft's diagnostic pattern) and **resumable
embedding**. If it ever becomes always-on, revisit a watchdog.

---

## What we deliberately DROP from Weft (not applicable)

- **The hermes-agent overlay + 5-tier extension ladder** — FreedomFromSNS isn't a Hermes overlay; it's a standalone app.
- **Mode A / B / C parity, apicascade cascade, advisor/critic tiers** — one chat, two modes (fast / agent), one provider.
- **The agent-framework bank** — trace spine, dspy, deepeval, kanban, cron, delegation, memory plugins, the self-improvement flywheel. All Weft-internal; none fits a single-user archive browser.
- **Obsidian/second-brain machinery** — *except* one free win: the `spaces-data/*.md` rows are already a valid Obsidian vault (inherited from fbbackup), so "open your archive in Obsidian" is a near-zero-cost feature if wanted.

---

**The one-line filter:** keep the North Star, the coding guidelines, deterministic-
over-LLM, privacy-by-construction, and `doctor`; adapt free-first and reliability
to a single-user local tool; drop the agent-framework and overlay machinery; and
don't fake a flywheel — this is a tool, and a good one.
