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
| **Nomic Embed v1.5** | 137M | tiny, **8K context** (rare under 500M), MRL, fully open | likely the best default-swap; in fastembed |
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

## Build order (when pursued)

1. **Swap the local embedding default** to Nomic v1.5 (verify fastembed/ONNX);
   expose a small picker; use MRL truncation for large archives. (S)
2. **Local chat (Ollama / 4-bit GGUF)** as a third Phase-A chat option; RAG-only
   synthesis through it; bundle/guide the runtime. (M)
3. **Ternary Bonsai 1.7B** once a packaged cross-OS ternary runtime exists. (M, later)

## Sources
- PrismML Ternary Bonsai: <https://prismml.com/news/ternary-bonsai>, <https://www.prnewswire.com/news-releases/prismml-introduces-ternary-bonsai-model-family-302745151.html>
- Nomic Embed v1.5 (137M, 8K, MRL): <https://www.nomic.ai/blog/posts/nomic-embed-text-v1>
- EmbeddingGemma (300M, MRL): <https://huggingface.co/google/embeddinggemma-300m>
- BGE-M3 (560M, hybrid): <https://huggingface.co/BAAI/bge-m3>
- fastembed supported models: <https://qdrant.github.io/fastembed/examples/Supported_Models/>
