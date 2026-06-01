"""fbbackup CLI — turn a Facebook export into a browsable, searchable archive.

    fbbackup setup     first-run wizard: find data → build → open (Tier 0)
    fbbackup parse     export JSON  → index/posts.jsonl + media-manifest
    fbbackup build     index        → spaces-data/<year>/*.md  (markdown rows)
    fbbackup embed     spaces-data  → index/embeddings.npy  (semantic search)
    fbbackup index     parse + build + embed  (the whole pipeline, one command)
    fbbackup serve     run the standalone timeline viewer
    fbbackup share     expose the running dashboard via a Cloudflare quick tunnel
    fbbackup export-static  index → a self-contained static site (browse + keyword)
    fbbackup publish   deploy a static export to a free host (GitHub/Cloudflare/…)
    fbbackup status     what's present (export? index? rows? embeddings?)

Paths resolve in this order: CLI flag > FBBACKUP_* env > config.toml > default.
Everything is written under FBBACKUP_HOME (default: the current directory); the
Facebook export is treated as READ-ONLY and never modified.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def _home() -> Path:
    """Where state lives (config.toml, index/, spaces-data/, .env).

    Resolution: FBBACKUP_HOME wins; else if the current dir is a project (has a
    config.toml) use it — the dev/repo workflow; else a stable per-user dir,
    ~/FreedomFromSNS, so an installed `ffs` run from any cwd always finds its data
    instead of scattering state wherever it was launched."""
    env = os.environ.get("FBBACKUP_HOME")
    if env:
        return Path(env).expanduser()
    if (Path.cwd() / "config.toml").is_file():
        return Path.cwd()
    return Path.home() / "ffs"   # ~/ffs (= C:\Users\<you>\ffs) — short, findable, no admin


def _load_env() -> None:
    """Load FBBACKUP_HOME/.env into the process env (existing vars win), so the
    Gemini key is available to embed + chat without exporting it by hand."""
    p = _home() / ".env"
    if not p.is_file():
        return
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _load_config() -> dict:
    """Read FBBACKUP_HOME/config.toml if present (best-effort)."""
    p = _home() / "config.toml"
    if not p.is_file():
        return {}
    try:
        import tomllib
        return tomllib.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001 — missing/old toml shouldn't break the CLI
        print(f"warning: could not read {p}: {e}", file=sys.stderr)
        return {}


def _resolve(flag: str | None, env: str, cfg_val, default) -> str:
    """flag > env var > config value > default."""
    if flag:
        return flag
    if os.environ.get(env):
        return os.environ[env]
    if cfg_val:
        return str(cfg_val)
    return str(default)


def _abs(path: str) -> Path:
    """Relative paths resolve under FBBACKUP_HOME; absolute paths pass through."""
    p = Path(path).expanduser()
    return p if p.is_absolute() else _home() / p


def _paths(args) -> dict[str, Path]:
    cfg = _load_config()
    exp = cfg.get("export", {})
    out = cfg.get("output", {})
    export_root = _abs(_resolve(getattr(args, "export", None), "FBBACKUP_EXPORT_ROOT",
                                exp.get("root"), "data"))   # default: ~/ffs/data
    index_dir = _abs(_resolve(getattr(args, "index", None), "FBBACKUP_INDEX",
                              out.get("dir"), "index"))
    spaces_root = _abs(_resolve(getattr(args, "spaces", None), "FBBACKUP_SPACES_ROOT",
                                None, "spaces-data"))
    return {"export": export_root, "index": index_dir, "spaces": spaces_root, "cfg": cfg}


# ── commands ─────────────────────────────────────────────────────────────────
def cmd_parse(args) -> int:
    from fbbackup.parse import parse
    p = _paths(args)
    if not p["export"].is_dir():
        print(f"✗ export folder not found: {p['export']}\n"
              f"  Download it from Facebook (Settings → Your Information → Download "
              f"Your Information → JSON → Posts), unzip it, and point --export at it.",
              file=sys.stderr)
        return 2
    print(f"parsing {p['export']} → {p['index']} …", flush=True)
    res = parse(p["export"], p["index"])
    print(f"✓ parsed {res.get('posts', '?')} posts", flush=True)
    return 0


def cmd_build(args) -> int:
    from fbbackup.materialize import materialize
    p = _paths(args)
    print(f"materializing {p['index']} → {p['spaces']} …", flush=True)
    res = materialize(p["index"], p["spaces"])
    print(f"✓ wrote {res.get('written', '?')} rows "
          f"(new={res.get('new', '?')}, updated={res.get('updated', '?')})", flush=True)
    return 0


def cmd_embed(args) -> int:
    from fbbackup.embed import embed
    p = _paths(args)
    res = embed(p["spaces"], p["index"])
    print(f"✓ embedded {res.get('count', '?')} rows via {res.get('provider', '?')} "
          f"(dim={res.get('dim', '?')})", flush=True)
    return 0


def cmd_index(args) -> int:
    """The whole pipeline: parse → build → embed."""
    for step in (cmd_parse, cmd_build, cmd_embed):
        rc = step(args)
        if rc != 0:
            return rc
    print("✓ index ready — start the dashboard and open the FB Browser.", flush=True)
    return 0


def cmd_serve(args) -> int:
    from fbbackup.ffs_server import serve
    p = _paths(args)
    cfg_serve = p["cfg"].get("serve", {})
    chat_model = (p["cfg"].get("gemini", {}) or {}).get("chat_model", "gemini-flash-latest")
    host = args.host or os.environ.get("FBBACKUP_HOST") or cfg_serve.get("host", "127.0.0.1")
    port = int(args.port or os.environ.get("FBBACKUP_PORT") or cfg_serve.get("port", 8282))
    print(f"FreedomFromSNS → http://{host}:{port}  (chat: {chat_model}; Ctrl-C to stop)", flush=True)
    serve(p["spaces"], p["export"], host=host, port=port, chat_model=chat_model,
          reload=bool(getattr(args, "reload", False)))
    return 0


def cmd_setup(args) -> int:
    """First-run wizard: pick a language, auto-locate the Facebook export, then
    parse + build and open the browser at Tier 0 (browse + keyword search — no
    AI key, no model download). Semantic search and chat are optional in-app
    unlocks. The goal is the fewest possible questions before the archive appears.
    """
    from fbbackup import setup as wiz
    from fbbackup.parse import parse
    from fbbackup.materialize import materialize

    home = _home()
    home.mkdir(parents=True, exist_ok=True)   # first run: create the per-user state dir
    lang = args.lang or wiz.detect_lang()
    if not args.lang and not args.yes:  # offer a language choice unless told
        try:
            pick = input(wiz.t(lang, "lang_prompt", d=("한국어" if lang == "ko" else "English"))).strip()
            lang = {"1": "en", "2": "ko"}.get(pick, lang)
        except EOFError:
            pass

    def say(key, **kw):
        print(wiz.t(lang, key, **kw), flush=True)

    say("welcome")

    # 1. Find the data — ask nothing if exactly one export is found.
    if args.export:
        chosen_root = _abs(args.export)
    else:
        say("searching")
        cands = wiz.locate_export()
        chosen = None
        if len(cands) == 1 or (cands and args.yes):
            chosen = cands[0]
            say("found_one", path=chosen.get("marker", chosen["root"]))
        elif len(cands) > 1:
            say("found_many", n=len(cands))
            for i, c in enumerate(cands, 1):
                print(f"    [{i}] {c.get('marker', c['root'])}"
                      f"{'  (zip)' if c['kind'] == 'zip' else ''}", flush=True)
            try:
                sel = input(wiz.t(lang, "choose")).strip()
            except EOFError:
                sel = ""
            idx = (int(sel) - 1) if sel.isdigit() and 1 <= int(sel) <= len(cands) else 0
            chosen = cands[idx]
        if chosen is None:
            say("none_found")
            try:
                manual = input(wiz.t(lang, "enter_path")).strip()
            except EOFError:
                manual = ""
            if not manual:
                return 2
            chosen = {"kind": "folder", "root": _abs(manual)}
        if chosen["kind"] == "zip":
            say("unzipping", path=chosen["root"])
            chosen_root = wiz.unzip_export(Path(chosen["root"]), home)
        else:
            chosen_root = Path(chosen["root"])

    wiz.set_export_root(home, chosen_root)
    say("using", path=chosen_root)

    # 2. Process to Tier 0 — parse + build (fast, deterministic; no embedding).
    p = _paths(args)  # re-reads config.toml → now points at the chosen export
    if not p["export"].is_dir():
        say("not_export")
        return 2
    import contextlib
    import io
    say("parsing")
    try:
        with contextlib.redirect_stdout(io.StringIO()):  # keep the wizard's output clean + localized
            res = parse(p["export"], p["index"])
    except SystemExit as e:
        say("no_posts")
        if e.code:
            print(str(e.code), file=sys.stderr)
        return 2
    say("parsed", n=res.get("posts", "?"))
    say("building")
    with contextlib.redirect_stdout(io.StringIO()):
        bres = materialize(p["index"], p["spaces"])
    say("built", n=bres.get("written", "?"))

    # 3. Tier 0 is ready; AI tiers are optional unlocks (surfaced in-app).
    say("tier0")
    say("tier1_hint")
    say("tier2_hint")

    # 4. Open the browser and serve (the wow moment).
    if args.no_serve:
        return 0
    from fbbackup.ffs_server import serve
    cfg_serve = p["cfg"].get("serve", {})
    chat_model = (p["cfg"].get("gemini", {}) or {}).get("chat_model", "gemini-flash-latest")
    host = args.host or cfg_serve.get("host", "127.0.0.1")
    port = int(args.port or cfg_serve.get("port", 8282))
    url = f"http://{host}:{port}"
    say("opening", url=url)
    if not args.no_open:
        import threading
        import webbrowser
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()  # after the server is up
    serve(p["spaces"], p["export"], host=host, port=port, chat_model=chat_model)
    return 0


def cmd_share(args) -> int:
    """Expose a locally-running server publicly via a Cloudflare quick tunnel
    (no account, ephemeral *.trycloudflare.com URL)."""
    if not _which("cloudflared"):
        print("✗ cloudflared not found on PATH.\n"
              "  Install it: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/",
              file=sys.stderr)
        return 2
    url = f"http://localhost:{args.port}"
    print(f"opening a public tunnel to {url} … (Ctrl-C to stop sharing)", flush=True)
    print("⚠  this publishes whatever the server exposes — use the dashboard's "
          "public read-only Share for a safe public archive.", flush=True)
    return subprocess.call(["cloudflared", "tunnel", "--url", url])


def cmd_export_static(args) -> int:
    """index/posts.jsonl → a self-contained static site (browse + keyword search,
    no backend) you can publish anywhere. The LOCAL app keeps the full experience."""
    from fbbackup.export_static import export_static
    p = _paths(args)
    out = _abs(args.out or "static-site")
    res = export_static(p["index"], out, media_mode=args.media)
    print(f"✓ static site → {res['out']}", flush=True)
    print(f"  {res['posts']} posts · {res['media_copied']} media · "
          f"{res['files']} files · {res['size_mb']} MB", flush=True)
    if args.media == "copy" and res["size_mb"] > 900:
        print("  ⚠ >900 MB — over GitHub Pages' 1 GB cap. Use --media omit, or "
              "publish to Cloudflare Pages/Netlify.", flush=True)
    print(f"  preview: cd {res['out']} && python3 -m http.server 8000", flush=True)
    print(f"  publish: fbbackup publish --target github-pages --dir {res['out']}", flush=True)
    return 0


def cmd_publish(args) -> int:
    from fbbackup.export_static import publish, PUBLISH_TARGETS, recommend_sharing
    if args.target == "list" or not args.target:
        print("publish targets (static archive — keyword search, no backend):\n")
        for k, t in sorted(PUBLISH_TARGETS.items(), key=lambda kv: kv[1]["easiest"]):
            print(f"  {k:18} {t['label']:18} {t['limits']}")
            print(f"  {'':18} ↳ {t['best_for']}  · sign up: {t['signup']}")
        print("\nrun: fbbackup publish --target <name> --dir <static-site> [--open-signup]")
        return 0
    if args.target == "recommend":
        p = _paths(args)
        posts = p["index"] / "posts.jsonl"
        n = sum(1 for _ in posts.open(encoding="utf-8")) if posts.is_file() else 0
        media = sum(line.count('"abs_path"') for line in posts.open(encoding="utf-8")) if posts.is_file() else 0
        rec = recommend_sharing(n, media * 0.4, media)  # ~0.4 MB/photo estimate
        print(f"▸ {rec['headline']}\n  {rec['why']}")
        if rec.get("share"):
            print(f"  {rec['share']}")
        if rec.get("publish"):
            print(f"  best host: {rec['publish']['target']} — {rec['publish']['why']}")
        return 0
    return publish(args.target, _abs(args.dir or "static-site"), open_signup=args.open_signup)


def cmd_status(args) -> int:
    p = _paths(args)
    posts = p["index"] / "posts.jsonl"
    emb = p["index"] / "embeddings.npy"
    n_posts = sum(1 for _ in posts.open(encoding="utf-8")) if posts.is_file() else 0
    n_rows = sum(1 for _ in p["spaces"].rglob("*.md")) if p["spaces"].is_dir() else 0
    print(f"FBBACKUP_HOME : {_home()}")
    print(f"export        : {p['export']}  {'✓' if p['export'].is_dir() else '✗ missing'}")
    print(f"index         : {posts}  {'✓ ' + str(n_posts) + ' posts' if n_posts else '✗ run `fbbackup parse`'}")
    print(f"rows          : {p['spaces']}  {'✓ ' + str(n_rows) + ' md' if n_rows else '✗ run `fbbackup build`'}")
    print(f"embeddings    : {emb}  {'✓' if emb.is_file() else '✗ run `fbbackup embed`'}")
    return 0


def cmd_doctor(args) -> int:
    """Plain-language health check — what's working, what needs fixing, and the
    exact command to fix it. (Borrowed from Weft's `doctor` pattern; serves the
    'a non-technical person can get unstuck' goal.)"""
    import urllib.error
    import urllib.request

    p = _paths(args)
    state = {"ok": True}

    def line(status: str, label: str, msg: str) -> None:
        if status == "fail":
            state["ok"] = False
        icon = {"ok": "✓", "warn": "⚠", "fail": "✗"}[status]
        print(f"  {icon} {label:14} {msg}")

    print("FreedomFromSNS — doctor\n")
    line("ok" if p["export"].is_dir() else "fail", "export",
         str(p["export"]) if p["export"].is_dir()
         else "not found  → unzip your Facebook (JSON) export and set [export].root in config.toml")

    from fbbackup.embed import gemini_key
    key = gemini_key()
    if not key:
        line("fail", "Gemini key", "missing  → put GEMINI_PAID_API_KEY=… in .env")
    else:
        try:
            body = json.dumps({"content": {"parts": [{"text": "ok"}]}, "taskType": "RETRIEVAL_QUERY"}).encode()
            req = urllib.request.Request(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={key}",
                data=body, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=15).read()
            line("ok", "Gemini key", f"valid (…{key[-4:]})")
        except urllib.error.HTTPError as e:
            line("fail", "Gemini key", f"rejected (HTTP {e.code})  → check the key and that billing is on")
        except Exception as e:  # noqa: BLE001
            line("warn", "Gemini key", f"could not verify — offline? ({str(e)[:40]})")

    posts = p["index"] / "posts.jsonl"
    n = sum(1 for _ in posts.open(encoding="utf-8")) if posts.is_file() else 0
    line("ok" if n else "fail", "index", f"{n} posts" if n else "missing  → run `ffs parse`")
    nr = sum(1 for _ in p["spaces"].rglob("*.md")) if p["spaces"].is_dir() else 0
    line("ok" if nr else "fail", "rows", f"{nr} rows" if nr else "missing  → run `ffs build`")

    meta = p["index"] / "embed-meta.json"
    if (p["index"] / "embeddings.npy").is_file():
        try:
            m = json.loads(meta.read_text(encoding="utf-8"))
            line("ok", "embeddings", f"{m.get('count', '?')} × {m.get('dim', '?')}d ({m.get('provider', '?')})")
        except Exception:  # noqa: BLE001
            line("ok", "embeddings", "present")
    else:
        line("warn", "embeddings", "missing  → run `ffs embed` (semantic search + chat need it)")

    port = int((p["cfg"].get("serve", {}) or {}).get("port", 8282))
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/api/meta", timeout=3).read()
        line("ok", "server", f"running on :{port}")
    except Exception:  # noqa: BLE001
        line("warn", "server", f"not running on :{port}  → run `ffs serve`")

    print("\n" + (f"✓ all set — open http://127.0.0.1:{port}" if state["ok"]
                  else "✗ fix the ✗ items above, then re-run `ffs doctor`"))
    return 0 if state["ok"] else 1


def _which(name: str) -> str | None:
    from shutil import which
    return which(name)


# ── parser ───────────────────────────────────────────────────────────────────
def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="ffs", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(sp, *, export=False, index=False, spaces=False):
        if export:
            sp.add_argument("--export", help="Facebook export folder (read-only)")
        if index:
            sp.add_argument("--index", help="index dir (posts.jsonl, embeddings)")
        if spaces:
            sp.add_argument("--spaces", help="spaces-data dir (markdown rows)")

    st = sub.add_parser("setup", help="first-run wizard: find data → build → open (Tier 0)")
    common(st, export=True, index=True, spaces=True)
    st.add_argument("--lang", choices=["en", "ko"], help="UI language (default: OS locale)")
    st.add_argument("--yes", action="store_true", help="non-interactive: accept the newest export found")
    st.add_argument("--host"); st.add_argument("--port")
    st.add_argument("--no-serve", action="store_true", help="stop after build; don't start the server")
    st.add_argument("--no-open", action="store_true", help="serve but don't auto-open a browser")

    common(sub.add_parser("parse", help="export → index/posts.jsonl"), export=True, index=True)
    common(sub.add_parser("build", help="index → spaces-data markdown rows"), index=True, spaces=True)
    common(sub.add_parser("embed", help="spaces-data → embeddings.npy"), index=True, spaces=True)
    common(sub.add_parser("index", help="parse + build + embed"), export=True, index=True, spaces=True)

    sv = sub.add_parser("serve", help="run the standalone timeline viewer")
    common(sv, index=True)
    sv.add_argument("--host"); sv.add_argument("--port")
    sv.add_argument("--reload", action="store_true",
                    help="auto-reload the server on Python edits (dev)")

    sh = sub.add_parser("share", help="Cloudflare quick tunnel to a running server")
    sh.add_argument("--port", default="9119", help="local port to expose (default 9119)")

    ex = sub.add_parser("export-static", help="index → self-contained static site")
    common(ex, index=True)
    ex.add_argument("--out", help="output dir (default: static-site)")
    ex.add_argument("--media", choices=["copy", "omit", "link"], default="copy",
                    help="copy media into the site (default), omit it, or link to FB")

    pb = sub.add_parser("publish", help="deploy a static export to a free host")
    pb.add_argument("--target", help="github-pages | cloudflare-pages | netlify | surge | vercel | list | recommend")
    pb.add_argument("--dir", help="static-site dir to publish (default: static-site)")
    pb.add_argument("--open-signup", action="store_true", help="open the host's sign-up page in a browser")
    common(pb, index=True)

    common(sub.add_parser("status", help="show what's present"), export=True, index=True, spaces=True)
    common(sub.add_parser("doctor", help="health check — what works + how to fix what doesn't"),
           export=True, index=True, spaces=True)
    return ap


_DISPATCH = {
    "setup": cmd_setup,
    "parse": cmd_parse, "build": cmd_build, "embed": cmd_embed, "index": cmd_index,
    "serve": cmd_serve, "share": cmd_share, "status": cmd_status, "doctor": cmd_doctor,
    "export-static": cmd_export_static, "publish": cmd_publish,
}


def main(argv: list[str] | None = None) -> int:
    _load_env()
    args = _build_parser().parse_args(argv)
    try:
        return _DISPATCH[args.cmd](args)
    except KeyboardInterrupt:
        return 130
    except SystemExit as e:  # parse/materialize raise SystemExit on user errors
        if e.code and not isinstance(e.code, int):
            print(e.code, file=sys.stderr)
            return 1
        return int(e.code or 0)


if __name__ == "__main__":
    sys.exit(main())
