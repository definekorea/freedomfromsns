# FreedomFromSNS — Local models for the no-key / no-GPU tier (research + roadmap)

**Goal.** Make the *fully-offline* experience genuinely good for people with **no
API key and no powerful GPU** — the North Star's "works with whatever they have."
Two fronts: better **local embeddings** (Tier 1 semantic search) and, newly
viable, **local chat** (a Tier 2 that needs no key). Status: **research; not built.**

## Where we are today

- **Embeddings (local):** `embed.py` provider `local` = fastembed (ONNX, CPU),
  default `jina-embeddings-v3`-class. Model is configurable via
  `FBBACKUP_EMBED_MODEL`; the wizard (Phase A) installs `fastembed` on demand.
- **Chat (local):** none. Chat requires an API key (Gemini for embeddings+chat,
  or DeepSeek/etc. for chat). There is currently **no no-key chat**.

So the gap this note addresses: a stronger local embedding default, and a
**local chat option** so Tier 2 works offline on a normal laptop.

## 1. Better local embeddings (sub-1B, CPU-friendly)

All run on CPU, no key. **Matryoshka (MRL)** models can truncate vector dims
(e.g. 1024→256) to shrink `embeddings.npy` with little accuracy loss — directly
relevant since our index is a flat `.npy` we load into RAM.

| Model | Params | Why it fits us | Notes |
|---|---|---|---|
| **Nomic Embed v1.5** | 137M | tiny, **8K context** (rare under 500M), MRL, fully open | ⚠️ measured: OOMs at default batch + slow on CPU — *not* the CPU default (see tester table) |
| **MiniLM-L12 multilingual** (measured winner) | ~118M | 384-dim, multilingual KO+EN, fast on CPU | **the no-GPU default** per benchmarks below |
| **EmbeddingGemma** | 300M | MRL, strong **multilingual (100+)** — matches our KO+EN data | check fastembed/ONNX availability |
| **BGE-M3** | 560M | **hybrid** dense + sparse(BM25-like) + ColBERT in one pass; multilingual | heavier; enables hybrid search later |

**Cheap win:** the local default is one constant (`LOCAL_MODEL` / `FBBACKUP_EMBED_MODEL`).
Swapping to Nomic v1.5 (8K ctx helps long posts; MRL shrinks the index) or
offering EmbeddingGemma for multilingual is low-effort *if* fastembed/ONNX has
the weights. MRL truncation would also cut RAM/disk for large archives.

## 2. Local chat with no key — small quantized / ternary models

The new enabler is **extreme quantization**: ternary (1.58-bit) and 4-bit GGUF
models now run usable chat on **CPU / Apple Silicon**, no discrete GPU.

- **PrismML Ternary Bonsai** (verified, Apr 2026): 1.58-bit ternary weights
  {-1,0,+1}, family at **1.7B / 4B / 8B**, ~9× smaller than FP16, Apache-2.0 on
  Hugging Face; 8B ≈ 75.5 avg benchmark (just behind Qwen3-8B) and ~27 tok/s on an
  iPhone 17 Pro Max. The **1.7B** is the interesting one for a no-GPU laptop.
  Caveat: ternary needs a **matching runtime** (BitNet-style, e.g. `bitnet.cpp`) —
  not just stock llama.cpp — so adoption hinges on a packaged, cross-OS runtime.
- **General path (lower risk):** **Ollama** or **llama.cpp** with a small 4-bit
  GGUF (Qwen3-1.7B/4B, Llama-3.2-3B, Gemma-3-4B). Mature, cross-OS, one-binary-ish;
  slower + lower quality than frontier APIs but real and free.

**How it maps to our tiers.** Phase A already probes GPU/CPU. Extend the *chat*
choice the same way: capable hardware → offer a **local chat model** (download
once, run via the bundled runtime) as a third option beside "free/paid API key"
and "skip." RAG retrieval stays deterministic (embeddings); only synthesis moves
to the local model. The agentic tool-loop is Gemini-native, so local chat is
RAG-only (fine).

## Honest tradeoffs (the governor)

- Local chat on CPU is **slow** (seconds-per-reply) and **weaker** than Gemini —
  set expectations in the UI; keep "connect a key" as the recommended path when
  the user has one.
- Ternary needs a special runtime → packaging risk across Win/mac/Linux; the
  4-bit-GGUF-via-Ollama path is the safer first step, Bonsai an upgrade once a
  clean cross-OS ternary runtime is bundled.
- Bigger local embedding models cost CPU time at index build; MRL offsets storage.

## Flywheel audit verdict

**Borrow-the-pattern / adopt-as-plain-tool, opt-in, human-gated.** These are
capability upgrades to the existing tiers, not loops — they advance "free/offline
for everyone" without changing the architecture. Adopt behind the same
GPU-aware, skippable choice (Phase A), default to the safest option, and never
auto-download heavyweight models without the user picking it.

## The hardware tester — quick, reliable, and self-correcting

**Why this is now central.** Static specs *lie*. Measured on an 8-vCPU / 48 GB / no-GPU
box (WSL):

Measured via fastembed on an **8-vCPU / 48 GB / no-GPU** box (WSL), 150 real KO+EN
posts; "~24k" extrapolates to this archive's 24,346 posts:

| Model | Download | dim | CPU tps | Peak RAM | ~24k posts | No-GPU verdict |
|---|---|---|---|---|---|---|
| `paraphrase-multilingual-MiniLM-L12-v2` | 240 MB | 384 | **86.5** | 0.75 GB | **~4.7 min** | ✅ the default — multilingual, fast, light |
| `bge-small-en-v1.5` | 65 MB | 384 | 15.2 | 0.86 GB | ~27 min | English-only → weak for Korean |
| `nomic-embed-text-v1.5` | 130 MB | 768 | 4.1 (bs≤8) | 4.6 GB | ~1.6 h | ⚠️ **OOM-killed at default batch** (8K-ctx padding); slow |
| `intfloat/multilingual-e5-large` | 2.24 GB | 1024 | 2.8 | 2.3 GB | ~2.4 h | GPU or cloud key only |
| `jinaai/jina-embeddings-v3` (current class) | 2.29 GB | 1024 | 1.9 | 6.9 GB | ~3.5 h | GPU or cloud key only |

Two findings that no static heuristic predicts:
1. The 130 MB `nomic` **OOM-killed a process with 43 GB free** — its 8K context makes
   onnxruntime pad to enormous batches at the default batch size.
2. The 1024-dim multilingual heavyweights are **30–45× slower on CPU** (3.5 h vs ~5 min) —
   download size and params don't tell you this; only a real run does.

**Conclusions:** (a) on a no-GPU machine the only practical local embedder is a small
384-dim multilingual model — **switch the local default to `paraphrase-multilingual-
MiniLM-L12-v2`** (the speculative "Nomic is best" earlier in §1 is *wrong* on CPU); the
1024-dim models are for GPUs or the cloud-key path (which embeds via API, instant). (b) a
tiny real **micro-benchmark is the only reliable signal**, and the system must **back off**
when reality underperforms.

### Design — three layers

**1. Static probe (instant, < 50 ms) → a first guess.**
- CPU: logical + **physical** cores, and **ISA flags (AVX2 / AVX-512)** — these dominate
  onnxruntime CPU speed. Read `/proc/cpuinfo` (Linux), `sysctl machdep.cpu` (mac),
  registry/`platform` (Win).
- **Available** RAM, not total (`MemAvailable` in `/proc/meminfo`; `GlobalMemoryStatusEx`
  via ctypes on Win; `vm_stat` on mac). This is the load-bearing number.
- Accelerator: the best signal is **`onnxruntime.get_available_providers()`** (tells if
  CUDA / CoreML / DirectML is *actually usable*, not just present) + `nvidia-smi` for
  NVIDIA name/VRAM + Apple-Silicon detection. Disk free for downloads.

**2. Micro-benchmark (the reliable part, ~3–8 s, hard-timeout).**
- Load the smallest viable model once; embed a fixed **16–32 text sample (incl. one long
  one)** at a *safe small batch*; measure throughput + peak RSS **in a subprocess** (so an
  OOM/crash can't take down the wizard, and RSS is isolated — we learned this the hard way).
- Extrapolate: `projected_embed_time = corpus_size / tps`; `projected_peak_RAM` at the
  intended batch. Decide: **local** only if `projected_time` is acceptable **and**
  `projected_peak_RAM < ~0.6 × available`; else **back off** to a cloud key (or a
  smaller/faster model, or a smaller batch). A micro-bench that exceeds its timeout =
  "too slow" → back off.

**3. Runtime back-off (during the real background embed).**
- Pick `batch_size` from available RAM; **clamp hard for long-context models** (never the
  library default). 
- Watchdog on the resumable embed: if the rate is far below the micro-bench estimate, or
  the process is OOM-killed/stalls, surface *"Smart search is slow on your hardware —
  switch to a free key?"* (keyword search already works; embed is resumable + provider-
  tagged, so switching re-embeds cleanly).

### Best-practice notes for the quick test
- Cache the result keyed by a hardware fingerprint — don't re-run every launch.
- Always run probes/benches in a **subprocess with a timeout** (crash isolation).
- Browse + keyword search **never** depend on any of this — that's the floor that always works.
- The same micro-bench pattern decides **local chat** feasibility (tok/s on a tiny prompt)
  before offering a local chat model.

## Mobile (future) — see deployment doc

Browsing on mobile + eventually on-device hosting/processing is a roadmap item; the
plan lives in `deployment-and-publishing.md` (Mobile section). The hardware tester +
small-model findings above are the foundation for the on-device-processing question.

## Build order (when pursued)

1. ✅ **Local embedding = `paraphrase-multilingual-MiniLM-L12-v2` on CPU, always**
   (measured winner; *not* Nomic). `EMBED_MODELS` still lists `large` (multilingual-e5,
   1024-d) but **`recommend_embed()` no longer auto-picks it on GPU** (v0.1.25): a
   detected GPU often isn't actually usable by onnxruntime (e.g. cuDNN missing) and the
   big model then **stalled on CPU** ("smart indexing stuck at 0"). MiniLM is reliable
   everywhere and fast on CPU; `large`+GPU is opt-in via `FBBACKUP_EMBED_MODEL` +
   `FBBACKUP_EMBED_DEVICE=gpu`. The micro-bench now gates on **runnability (OOM)**, not
   speed (local is the default even if slow). Query embeds with the **corpus's recorded
   model** (meta), with a dim-mismatch guard. (S) — done.
2. ✅ **No-key local chat** — built (`fbbackup/localchat.py` + `ffs localchat`). We
   download a prebuilt `llama-server` (PrismML's llama.cpp fork, `prism-b8846-d104cf1`;
   carries the Q2_0 ternary kernels AND runs ordinary GGUFs — no compiler), run a
   loopback OpenAI server (:8284), and expose a no-key `local` chat provider the RAG
   path uses unchanged. Three curated models, switchable via `ffs localchat --model`:
   - **exaone** (default) — LG **EXAONE-3.5-2.4B-Instruct** Q4_K_M (~1.5 GB). Tested:
     correct Korean RAG (persia/iran + Jeju) with the most natural Korean. Best for a
     Korean archive.
   - **qwen3** — **Qwen3-1.7B** Q8 (~1.8 GB), multilingual; launched `--reasoning off`
     so it replies directly. Also correct on the Korean RAG tests.
   - **bonsai** — **Ternary-Bonsai-1.7B** Q2_0 (~0.45 GB), ultralight/English; FAILED
     the Korean RAG tests (English-centric). Kept for low-end/English use only.
   Validated end-to-end on Linux (download/extract/run/switch/chat). RAG-only; for top
   quality a Gemini key still wins.
3. ✅ **Setup auto-wires no-key chat**: local path downloads/starts EXAONE in the
   background and sets it as the chat provider (v0.1.15).
4. ✅ **Local AI CLI providers** (v0.1.26–27): `claude-cli` (`claude -p`), `codex-cli`
   (`codex exec`), `antigravity-cli` (`agy -p`) — `providers._cli_chat` shells out to a
   tool you already have installed + logged in (your own subscription, no key). Setup
   **prefers a working CLI** over downloading the local model (priority: Gemini key →
   working CLI → bundled local model → keyless-lazy-local).

## Sources
- PrismML Ternary Bonsai: <https://prismml.com/news/ternary-bonsai>, <https://www.prnewswire.com/news-releases/prismml-introduces-ternary-bonsai-model-family-302745151.html>
- Nomic Embed v1.5 (137M, 8K, MRL): <https://www.nomic.ai/blog/posts/nomic-embed-text-v1>
- EmbeddingGemma (300M, MRL): <https://huggingface.co/google/embeddinggemma-300m>
- BGE-M3 (560M, hybrid): <https://huggingface.co/BAAI/bge-m3>
- fastembed supported models: <https://qdrant.github.io/fastembed/examples/Supported_Models/>
