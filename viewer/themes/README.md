# Theme system — `viewer/themes/`

The entire look of FreedomFromSNS is driven by **design tokens** (CSS custom
properties). A **theme is one JSON file** in this folder that sets those tokens;
the whole stylesheet flows from them, so a single file repaints everything.
Switch themes with the 🎨 button in the filter bar (it cycles; the choice
persists). Add a theme by dropping a `.json` here — no code, no restart.

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

> "Accent themes" (Emerald / Azure / Crimson) override just
> `gold` + `gold-rgb` + `accent` + `on-accent` (+ a tuned `brand-fg`). Because
> tints use `var(--gold-rgb)`, the whole accent system — solids **and** tints —
> recolors coherently from those four values.

---

## Add / author a theme

1. Copy `00-default.json` to `NN-<name>.json` (pick `NN` for its cycle slot).
2. Change the tokens you want; delete the ones you keep at default (optional).
3. Reload — `home()` re-scans per request, so it's in the 🎨 cycle immediately.
4. Pick it with 🎨. To make it the default, name it to sort first.

**Contrast:** keep `on-accent` dark enough to read on the accent color, and
`txt`/`dim`/`faint` legible on `bg`.

---

## Known limitation (light themes)

A handful of one-off neutral greys (e.g. `#333`, `#ddd`, subtle `#16161x`
surfaces) are not yet tokenized — they read fine across **dark** themes but a
true **light** theme would need them promoted to tokens too. The token layer is
built to allow it (`shadow-rgb` / `hi-rgb` already exist for inverting
shadows/overlays); finishing the greys is the remaining work for light mode.
