"""Pluggable chat providers for FreedomFromSNS — connect any AI you have.

Self-contained (no Weft/apicascade dependency): a small catalog of providers and
a `chat_complete()` that dispatches by wire format. Most providers speak the
OpenAI `/chat/completions` shape (OpenAI, DeepSeek, OpenRouter, Groq, Mistral,
Cerebras, Ollama, even Gemini's openai-compat endpoint); Gemini's native API is
kept for its thinking control + the existing image grounding; Anthropic uses
`/v1/messages`. The North Star: "connect a free key, a paid key, or a local model."

Settings live in `<home>/settings.json` (provider + model choices); API keys live
in `<home>/.env` (secrets). Embeddings stay in embed.py (already pluggable).
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

# Catalog: id → label, wire format, base URL, the .env var holding its key, and
# starter fast/precise model ids (editable in the UI; some may drift — the user
# can change them). signup is shown in settings to get a key.
CHAT_PROVIDERS: dict[str, dict] = {
    "gemini": {"label": "Google Gemini", "format": "gemini", "key_env": "GEMINI_PAID_API_KEY",
               "base_url": "https://generativelanguage.googleapis.com/v1beta",
               "fast": "gemini-flash-latest", "precise": "gemini-3.5-flash",
               "signup": "https://aistudio.google.com/apikey"},
    "openai": {"label": "OpenAI", "format": "openai", "key_env": "OPENAI_API_KEY",
               "base_url": "https://api.openai.com/v1", "fast": "gpt-4o-mini", "precise": "gpt-4o",
               "signup": "https://platform.openai.com/api-keys"},
    "anthropic": {"label": "Anthropic (Claude)", "format": "anthropic", "key_env": "ANTHROPIC_API_KEY",
                  "base_url": "https://api.anthropic.com", "fast": "claude-3-5-haiku-latest",
                  "precise": "claude-3-5-sonnet-latest", "signup": "https://console.anthropic.com/settings/keys"},
    "deepseek": {"label": "DeepSeek", "format": "openai", "key_env": "DEEPSEEK_API_KEY",
                 "base_url": "https://api.deepseek.com/v1", "fast": "deepseek-chat", "precise": "deepseek-reasoner",
                 "signup": "https://platform.deepseek.com/api_keys"},
    "openrouter": {"label": "OpenRouter", "format": "openai", "key_env": "OPENROUTER_API_KEY",
                   "base_url": "https://openrouter.ai/api/v1", "fast": "google/gemini-2.5-flash",
                   "precise": "anthropic/claude-3.7-sonnet", "signup": "https://openrouter.ai/keys"},
    "groq": {"label": "Groq", "format": "openai", "key_env": "GROQ_API_KEY",
             "base_url": "https://api.groq.com/openai/v1", "fast": "llama-3.1-8b-instant",
             "precise": "llama-3.3-70b-versatile", "signup": "https://console.groq.com/keys"},
    "mistral": {"label": "Mistral", "format": "openai", "key_env": "MISTRAL_API_KEY",
                "base_url": "https://api.mistral.ai/v1", "fast": "mistral-small-latest",
                "precise": "mistral-large-latest", "signup": "https://console.mistral.ai/api-keys"},
    "cerebras": {"label": "Cerebras", "format": "openai", "key_env": "CEREBRAS_API_KEY",
                 "base_url": "https://api.cerebras.ai/v1", "fast": "llama3.1-8b", "precise": "llama-3.3-70b",
                 "signup": "https://cloud.cerebras.ai"},
    "ollama": {"label": "Ollama (local · offline)", "format": "openai", "key_env": "",
               "base_url": "http://localhost:11434/v1", "fast": "llama3.2", "precise": "llama3.1",
               "signup": "https://ollama.com"},
    # Bundled no-key local chat: PrismML Ternary Bonsai 1.7B on a loopback
    # llama-server we download + manage (see localchat.py). RAG-only; weak on
    # Korean — an offline/low-power option, not a frontier replacement.
    "bonsai": {"label": "Local · Bonsai 1.7B (offline, no key, no GPU)", "format": "openai", "key_env": "",
               "base_url": "http://127.0.0.1:8284/v1", "fast": "bonsai", "precise": "bonsai",
               "signup": "https://prismml.com/news/ternary-bonsai"},
}

# Embedding providers are implemented in embed.py; cataloged here for the UI.
EMBED_PROVIDERS: dict[str, dict] = {
    "gemini": {"label": "Google Gemini", "key_env": "GEMINI_PAID_API_KEY", "model": "gemini-embedding-001"},
    "openai": {"label": "OpenAI", "key_env": "OPENAI_API_KEY", "model": "text-embedding-3-small"},
    "local": {"label": "Local · offline (fastembed)", "key_env": "",
              "model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"},
}

_DEFAULTS = {
    "chat": {"provider": "gemini", "fast_model": "gemini-flash-latest", "precise_model": "gemini-3.5-flash"},
    "embedding": {"provider": "gemini", "model": "gemini-embedding-001"},
    # Guardrails applied to PUBLIC (shared-link) chat only — the local owner is never
    # limited. `public: false` lifts them entirely (for local-only use, local models,
    # or "I don't mind the cost"). topic_lock keeps public chat on-archive-topic.
    "limits": {"public": True, "topic_lock": True, "per_min": 6, "daily": 300, "allow_agent_public": False},
    # Optional login gate for the PUBLIC URL. scope "off" = anyone with the link can
    # browse (read-only); "site" = a passcode (login page) is required for the whole
    # site — e.g. "web access only for myself". The owner (local) is never gated.
    "access": {"scope": "off", "passcode": ""},
}


def home() -> Path:
    return Path(os.environ.get("FBBACKUP_HOME", os.getcwd())).expanduser()


# ── settings (provider + model choices) ──────────────────────────────────────
def load_settings() -> dict:
    s = {k: dict(v) for k, v in _DEFAULTS.items()}
    try:
        disk = json.loads((home() / "settings.json").read_text("utf-8"))
        for sect in ("chat", "embedding"):
            if isinstance(disk.get(sect), dict):
                s[sect].update({k: v for k, v in disk[sect].items() if v})
        if isinstance(disk.get("limits"), dict):     # allow False/0 (don't drop falsy)
            s["limits"].update({k: v for k, v in disk["limits"].items() if v is not None})
    except Exception:  # noqa: BLE001  (missing/corrupt → defaults)
        pass
    return s


def save_settings(s: dict) -> dict:
    cur = load_settings()
    for sect in ("chat", "embedding"):
        if isinstance(s.get(sect), dict):
            cur[sect].update({k: v for k, v in s[sect].items() if v is not None})
    if isinstance(s.get("limits"), dict):
        cur["limits"].update({k: v for k, v in s["limits"].items() if v is not None})
    (home() / "settings.json").write_text(json.dumps(cur, ensure_ascii=False, indent=2), "utf-8")
    return cur


# ── API keys (live in .env; written + hot-applied to the process env) ────────
def get_key(env_var: str) -> str:
    return (os.environ.get(env_var) or "").strip() if env_var else ""


def set_key(env_var: str, value: str, process: bool = True) -> None:
    """Upsert KEY=value in <home>/.env. process=True also applies it to the
    running server (right for API keys); process=False writes the file only —
    used for the embedding provider/model, which must NOT change the live
    server's query embedding until the corpus is re-embedded."""
    if not env_var:
        return
    value = (value or "").strip()
    if process:
        os.environ[env_var] = value
    p = home() / ".env"
    lines = p.read_text("utf-8").splitlines() if p.is_file() else []
    out, found = [], False
    for ln in lines:
        if ln.strip().startswith(env_var + "="):
            out.append(f"{env_var}={value}"); found = True
        else:
            out.append(ln)
    if not found:
        out.append(f"{env_var}={value}")
    p.write_text("\n".join(out) + "\n", "utf-8")


def _gemini_key() -> str:
    for v in ("GEMINI_PAID_API_KEY", "GEMINI_API_KEY", "GEMINI_FREE_API_KEY"):
        if os.environ.get(v):
            return os.environ[v].strip()
    return ""


def provider_status() -> dict:
    """Per-provider: configured (has key) — for the settings UI."""
    out = {}
    for pid, c in CHAT_PROVIDERS.items():
        has = True if not c["key_env"] else bool(get_key(c["key_env"]) or (pid == "gemini" and _gemini_key()))
        out[pid] = {"label": c["label"], "key_env": c["key_env"], "configured": has,
                    "fast": c["fast"], "precise": c["precise"], "signup": c["signup"], "format": c["format"]}
    return out


# ── HTTP ─────────────────────────────────────────────────────────────────────
def _post(url: str, body: dict, headers: dict, timeout: float = 120) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _budget(model: str, settings: dict) -> tuple[int, bool]:
    """maxOutputTokens + whether this is the precise (thinking) lane."""
    precise = model == settings["chat"].get("precise_model")
    return (8192, True) if precise else (4096, False)


def _gemini_native(key, model, messages, system, max_tokens, thinking, temperature):
    contents = [{"role": "model" if m.get("role") == "assistant" else "user",
                 "parts": [{"text": (m.get("content") or "").strip()}]}
                for m in messages if (m.get("content") or "").strip()]
    if not contents:
        contents = [{"role": "user", "parts": [{"text": "안녕하세요"}]}]
    gen = {"maxOutputTokens": max_tokens, "temperature": temperature}
    if not thinking:                       # fast lane → no reasoning tokens
        gen["thinkingConfig"] = {"thinkingBudget": 0}
    url = f"{CHAT_PROVIDERS['gemini']['base_url']}/models/{model}:generateContent?key={key}"
    d = _post(url, {"systemInstruction": {"parts": [{"text": system}]}, "contents": contents,
                    "generationConfig": gen}, {"Content-Type": "application/json"})
    c = (d.get("candidates") or [{}])[0]
    return "".join(p.get("text", "") for p in (c.get("content") or {}).get("parts", [])).strip()


def _openai_chat(base, key, model, messages, system, max_tokens, temperature):
    msgs = ([{"role": "system", "content": system}] if system else []) + \
           [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in messages]
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    d = _post(base.rstrip("/") + "/chat/completions",
              {"model": model, "messages": msgs, "max_tokens": max_tokens, "temperature": temperature}, headers)
    return ((d.get("choices") or [{}])[0].get("message") or {}).get("content", "").strip()


def _anthropic_chat(base, key, model, messages, system, max_tokens, temperature):
    msgs = [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in messages if m.get("content")]
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
    d = _post(base.rstrip("/") + "/v1/messages",
              {"model": model, "system": system, "messages": msgs,
               "max_tokens": max_tokens, "temperature": temperature}, headers)
    return "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text").strip()


def chat_complete(messages: list[dict], system: str, model: str, settings: dict | None = None) -> str:
    """Send a chat turn to the active provider and return the answer text. Image
    grounding (the [[IMG:n]] markers) is applied by the caller, so this is plain
    text in / text out and works for any provider."""
    settings = settings or load_settings()
    pid = settings["chat"].get("provider", "gemini")
    cat = CHAT_PROVIDERS.get(pid) or CHAT_PROVIDERS["gemini"]
    max_tokens, thinking = _budget(model, settings)
    try:
        if cat["format"] == "gemini":
            key = _gemini_key() or get_key(cat["key_env"])
            if not key:
                raise RuntimeError("Gemini API 키가 설정되지 않았습니다. 설정에서 키를 입력하세요. "
                                   "/ No Gemini key — connect one in Settings.")
            return _gemini_native(key, model, messages, system, max_tokens, thinking, 0.5)
        key = get_key(cat["key_env"])
        if cat["key_env"] and not key:
            raise RuntimeError(f"{cat['label']} 키가 없습니다. 설정에서 입력하세요. "
                               f"/ No {cat['label']} key — connect one in Settings.")
        if cat["format"] == "anthropic":
            return _anthropic_chat(cat["base_url"], key, model, messages, system, max_tokens, 0.5)
        return _openai_chat(cat["base_url"], key, model, messages, system, max_tokens, 0.5)
    except urllib.error.HTTPError as e:
        detail = ""
        try:                                   # the upstream API's own error message — the real reason
            raw = e.read().decode("utf-8", "replace")[:600]
            err = (json.loads(raw) or {}).get("error")
            detail = (err.get("message") if isinstance(err, dict) else err) or raw
        except Exception:  # noqa: BLE001
            detail = ""
        if e.code in (401, 403):
            raise RuntimeError(
                f"{cat['label']} 키가 거부되었습니다 (HTTP {e.code}). 키가 맞는지, 그리고 해당 API가 "
                f"활성화/결제됐는지 확인하세요. / {cat['label']} rejected the key (HTTP {e.code}) — "
                f"check the key and that the API is enabled. [{str(detail)[:300]}]")
        raise RuntimeError(f"{cat['label']} API 오류 (HTTP {e.code}). [{str(detail)[:300]}]")
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"{cat['label']}에 연결할 수 없습니다 — 로컬 모델(Ollama 등)이라면 실행 중인지 확인하세요. "
            f"/ Couldn't reach {cat['label']} — if it's a local model (e.g. Ollama), is it running? "
            f"({getattr(e, 'reason', '')})")


def test_chat(provider: str, model: str) -> tuple[bool, str]:
    """Tiny live call to verify a provider+key+model works. Returns (ok, detail)."""
    settings = {"chat": {"provider": provider, "precise_model": "__none__"}}
    try:
        out = chat_complete([{"role": "user", "content": "Reply with the word: ok"}],
                            "You are a test. Reply with a single word.", model, settings)
        return (bool(out), out[:80] or "(empty)")
    except urllib.error.HTTPError as e:  # noqa: F821
        try:
            msg = json.loads(e.read()).get("error", {})
            msg = msg.get("message") if isinstance(msg, dict) else str(msg)
        except Exception:
            msg = f"HTTP {e.code}"
        return (False, str(msg)[:160])
    except Exception as e:  # noqa: BLE001
        return (False, str(e)[:160])
