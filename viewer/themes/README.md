# Theme system — `viewer/themes/`

The entire look of FreedomFromSNS is driven by **design tokens** (CSS custom
properties). A **theme is one JSON file** in this folder that sets those tokens;
the whole stylesheet flows from them, so a single file repaints everything.
Pick a theme from the 🎨 menu in the filter bar (a swatch + name per theme;
the choice persists). Add a theme by dropping a `.json` here — no code, no
restart.

**Shipped set (36):**

*Light themes (16):*
- 5 major-site light UIs (`01`–`05`): Primary Pop (Google), Amber Linen
  (Amazon), Sapphire Mist (Facebook), Scarlet Paper (YouTube), Electric Violet
  (Yahoo).
- 10 from Framer's *10 elegant palettes* (`08`–`17`): Earth Tones, Vibrant
  Greens, Warm Neutrals, Maroon Mood, Bold Orange, Cool Blues, Minimal,
  Pastels, Vibrant Blues, Power Purple.
- `35` **Gallery** — a white-cube editorial theme (white bg, black ink, thin
  rules; the photos supply the colour), after the CCA Tel Aviv-Yafo site.

*Dark themes (20):*
- `00-default` **Gold Noir**, `06` Mocha Mousse, `07` Neon.
- 16 from a palette gallery (`18`–`33`): Morning Sky, Burgundy Rose, Cocoa Lime,
  Barn Sage, Cerulean, Evergreen, Jade Mist, Toffee, Coral Reef, Dusty Indigo,
  Tropical Punch, Harvest, Deep Ocean, Pop Art, Dusty Dune, Espresso.
- `34` **Greyscale** — monochrome (silver accent on the neutral dark base).

Dark themes take their palette's signature colour as the accent and tune the
base to that hue. A **light theme must be a full token set** (it inverts
surfaces + text) with `hi-rgb: 0,0,0` — see `01-primary-pop` (a coloured light
theme) or `35-gallery` (a monochrome one) as templates.

---

## How it works

1. `viewer/fb-app.css` defines the **default values** of every token in `:root`
   (the "Gold Noir" look) and uses **only** those tokens everywhere. With JS
   off, the default theme still renders.
2. `fbbackup/ffs_server.py` → `home()` scans `viewer/themes/*.json` (sorted by
   filename, so `00-default` is first), and injects them as
   `window.FFS.themes = [{name, tokens}, …]`.
3. A tiny `<head>` script in `index.html` applies the **persisted** theme before
   first paint (no flash). `fb-app.js` (`applyTheme` / `setTheme`) handles
   switching at runtime: it **clears all theme-set `:root` properties, then
   applies the chosen theme** — so a theme file may be **partial** (list only
   the tokens it changes; the rest fall back to the CSS `:root` default).
4. The chosen index is remembered in `localStorage["ffs.theme"]`.

---

## Theme file format

```jsonc
{
  "name": "Emerald",          // shown in the 🎨 tooltip
  "tokens": {                 // bare token names (no leading --); applied as :root vars
    "gold": "#2dd4a7",
    "gold-rgb": "45,212,167",
    "accent": "#5eead4",
    "on-accent": "#04130d"
  }
}
```

- **Order:** files are sorted by filename; prefix `00-`, `01-`, … to control the
  cycle order. `00-default.json` should stay first (it's the full reference).
- **Partial vs full:** `00-default.json` lists every token (the canonical
  reference). Variant themes only need the tokens they override.

---

## Token reference

Colors are hex; the `*-rgb` tokens are **`R,G,B` triples** (no `rgb()` wrapper)
so tints and shadows — written `rgba(var(--x-rgb), a)` — re-tint with the theme.

| Token | Role |
|---|---|
| `bg`, `bg-rgb` | page background (rgb form used for the sticky header scrim) |
| `bg2` | cards, bubbles, raised surfaces |
| `bg3` | inputs, chips, controls |
| `line` | borders / dividers |
| `shadow-rgb` | drop shadows + modal scrims (`0,0,0` on dark themes) |
| `hi-rgb` | faint light overlays (even-row tint, etc.) |
| `txt` | body text |
| `fg` | slightly brighter text (controls, hovers) |
| `fg-bright` | strongest text (hover headings) — usually white |
| `dim` | secondary text |
| `faint` | tertiary text (dates, counts, placeholders) |
| `gold`, `gold-rgb` | **the accent** — brand, active tab, primary buttons, tints |
| `accent` | brighter accent (focus rings, slider/hover highlights) |
| `on-accent` | text/icon **on** an accent-filled surface (near-black on gold) |
| `brand-fg`, `brand-fg-2` | wordmark base color (big / quieter-beside-emblem) |
| `red`, `red-rgb` | video / destructive / delete |
| `blue` | links |
| `green` | the "status/글" type accent |
| `rad`, `rad-pill` | corner roundness (cards / pills) |
| `font-base` | UI + body font stack |
| `font-display` | brand + calendar-title display font stack |

> A minimal "accent-only" theme overrides just `gold` + `gold-rgb` + `accent` +
> `on-accent` (+ a tuned `brand-fg`). Because tints use `var(--gold-rgb)`, the
> whole accent system — solids **and** tints — recolors coherently from those
> four values. The shipped brand/image themes go further and also retune the
> surfaces (`bg`/`bg2`/`bg3`/`line`) to sit in the palette's hue.

---

## Add / author a theme

1. Copy `00-default.json` to `NN-<name>.json` (pick `NN` for its cycle slot).
2. Change the tokens you want; delete the ones you keep at default (optional).
3. Reload — `home()` re-scans per request, so it's in the 🎨 cycle immediately.
4. Pick it with 🎨. To make it the default, name it to sort first.

**Contrast:** keep `on-accent` dark enough to read on the accent color, and
`txt`/`dim`/`faint` legible on `bg`.

---

## Light themes

Light themes are fully supported. The stylesheet routes **every** surface, text,
border and tint through tokens (`--sunken`/`--line2` cover the deep wells and
strong borders; `--blue-rgb`/`--green-rgb` cover the semantic tints), so a light
theme just needs to set light surfaces + dark text. The shipped `01`–`05` are
light. When authoring one:

- set `bg`/`bg2`/`bg3`/`sunken` light, `line`/`line2` to light greys;
- set `txt`/`fg`/`dim`/`faint` dark, and **`fg-bright` to near-black** (it's the
  strongest text, white only on dark themes);
- set **`hi-rgb: 0,0,0`** so faint overlays (even-row tint, etc.) darken;
- keep `shadow-rgb: 0,0,0` (shadows are dark on any background);
- pick `on-accent` to read on the accent (white on saturated blue/red/purple,
  near-black on a light/orange accent).
