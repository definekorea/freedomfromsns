# Brand logo set — `viewer/logo-candidates/`

The FreedomFromSNS brand mark in the top-left **cycles through designs when
clicked** (and the click also navigates Home). This folder holds the emblem
images; design 0 is always the typographic wordmark, rendered in code. Add,
replace, or remove emblems here — no code edits, no server restart.

---

## Location & wiring

| Thing | Where |
|---|---|
| Emblem images | `viewer/logo-candidates/*.{png,jpg,jpeg,webp,svg}` (this folder) |
| Auto-discovery | `fbbackup/ffs_server.py` → `home()` scans this folder, **sorts by filename**, appends `?v=<mtime>` (cache-bust), injects as `window.FFS.logos` |
| Render + rotation | `viewer/fb-app.js` → `LOGOS`, `renderBrand()`, the `.fb-brand` click handler |
| Styling | `viewer/fb-app.css` → `.fb-brand`, `.fb-brand .fa`, `.fb-brand.img`, `.fb-logo-img`, `.fb-logo-text` |

The rotation list is `LOGOS = [null].concat(window.FFS.logos)`:
- **index 0 = `null`** → the typographic wordmark (no image, drawn in code),
- **index 1…N** → the emblems in this folder, in filename order.

---

## Icon spec (emblems)

- **Aspect:** 1:1 (square). **Source size:** 1024×1024 (generated at the `1K` tier).
- **Format:** PNG preferred (JPG / WebP / SVG also accepted).
- **Palette:** warm gold `--gold` = `#e0c060` on a near-black charcoal
  background (`--bg` `#0a0a0a` … `#161616`). Match the app's gold-on-dark theme.
- **Style:** minimalist flat / line-art, rounded-square icon, generous negative
  space, centered, premium. **No baked-in text** — the name is added in code
  beside the icon (see below), so emblems stay legible and re-typesettable.
- **Displayed at:** `38×38px`, `object-fit: contain`, `border-radius: 9px`
  in the header (`.fb-logo-img`). Design for clarity at that small size.
- **Naming → order:** files are sorted by name, so prefix with `01-`, `02-`,
  `03-`, … to control the rotation order. Use short, kebab-case slugs
  (`01-monogram.png`).

Current set: `01-monogram.png` (FFS monogram + broken chain), `02-bird.png`
(bird leaving an open cage), `03-unplug.png` (notification dissolving into a
bird in flight).

---

## Lettering spec (the wordmark)

The wordmark is **FreedomFromSNS** with the **F · F · S** (Freedom · From · SNS)
picked out as accents, so "FFS" reads out of the full name.

- **Font:** `"Bebas Neue", "Pretendard Variable", Impact, sans-serif` — a
  condensed all-caps display face (so the wordmark renders uppercase).
- **Accent letters** (`.fa` spans on F / F / S): gold `--gold`, bold (700),
  slightly larger than the base, with a soft glow.

| Context | Base size | Base color | Accent (F·F·S) |
|---|---|---|---|
| Standalone wordmark (design 0) | `1.7rem`, letter-spacing `1.5px` | `#dcd8cc` | `1.32em`, gold, glow |
| Beside an emblem (`.fb-logo-text`) | `1.05rem`, letter-spacing `1px` | `#b3b0a6` (quieter) | `1.16em`, gold, no glow |

When an emblem is shown, the icon + the smaller wordmark sit in a flex row
(`.fb-brand.img`, `gap .5rem`) — the name stays visible but less prominent than
the standalone wordmark.

---

## Rotation method

1. Clicking `.fb-brand` runs: `S.logo = (S.logo + 1) % LOGOS.length` →
   persist to `localStorage["ffs.logo"]` → `renderBrand()` → `goHome()`.
   So one click **advances the design AND returns to Browse** (the brand
   doubles as the Home button; the Browse tab also goes Home).
2. The chosen index is remembered across reloads via `localStorage["ffs.logo"]`.
3. `renderBrand()` reads `LOGOS[S.logo % LOGOS.length]`: `null` → wordmark,
   else `<img class="fb-logo-img">` + `<span class="fb-logo-text">` wordmark.

---

## Add / replace / remove a design

- **Add:** drop an image here named to sort where you want it
  (e.g. `04-sunrise.png`). Reload the page — `home()` re-scans on every
  request, so it's in the rotation immediately. No code, no restart.
- **Replace:** overwrite an existing file. The `?v=<mtime>` cache-bust serves
  the new version on the next load.
- **Remove:** delete the file — it drops out of the rotation. (If a user's
  stored index now points past the end, the `% LOGOS.length` wraps it safely.)

---

## Regenerating emblems (nano-banana)

The current emblems were generated once with the **nano-banana** skill
(Gemini Flash Image). To make more in the same style:

```bash
export GEMINI_PAID_API_KEY=<key>        # from ~/.hermes/.env or ./.env
python3 ~/.claude/skills/nano-banana/scripts/nano_banana.py \
  -a 1:1 -r 1K -o viewer/logo-candidates/04-<slug>.png \
  -p "Minimalist app icon, <concept>, warm gold line-art on a deep charcoal-black \
background, elegant flat design with generous negative space, centered, modern, \
premium, no text"
```

Keep the recipe constant — **gold-on-dark, 1:1, flat/line-art, no text** — so a
new emblem drops cleanly into the set.
