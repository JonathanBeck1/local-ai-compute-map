# Phase 03c — Explicit MoE placement, measured against the automatic one

**Status:** done
**Date:** 2026-09-18
**Elapsed:** ~1.5 h
**Cost:** $0

## Goal

[Phase 03](03-local-model-endpoint.md) left a question open: Ollama splits a 30B MoE across CPU and GPU automatically and gets 53.6 tok/s. llama.cpp lets you place the expert tensors by hand. Does controlling it beat letting it decide?

## Hardware touched

The phase 02 box: RTX 4070, 12,282 MiB VRAM, 64 GB DDR4-3200, models on the SATA disk. Also the owner's desktop — three monitors, a Steam library — which turns out to matter to the answer.

## What I ran

The control that makes this a real comparison: **both engines were pointed at the same file.** Ollama stores models as GGUF blobs, world-readable at `-rw-r--r--`, so llama.cpp can mmap one read-only while Ollama keeps serving from it. No second download, no "equivalent" quant, no ambiguity about whether the weights match. Confirmed by parsing the header:

```
magic=GGUF version=3 tensors=579 kv_pairs=35
general.name               = Qwen3 Coder 30B A3B Instruct
general.architecture       = qwen3moe
general.file_type          = 15            (Q4_K_M)
qwen3moe.block_count       = 48            <- the sweep range
qwen3moe.expert_count      = 128
qwen3moe.expert_used_count = 8             <- ~3B active of 30.5B
```

Same weights, same prompt, same generated-token count, GPU idle before each configuration, warm-up discarded, five measured runs. llama.cpp from `ghcr.io/ggml-org/llama.cpp:server-cuda`, reading `timings.predicted_per_second`; Ollama reading `eval_count / eval_duration`. Same quantity, both sides.

The verdict rule was fixed **before** any numbers existed: |Δ| < 10%, or ranges that overlap at all, counts as no meaningful difference.

## Output

Short prompt, context 4096:

```
config                         VRAM        gen tok/s (5 runs)
llama.cpp  -ncmoe 19           --          DID NOT LOAD
llama.cpp  -ncmoe 20           11330 MiB   62.57   (62.44 - 62.80)
llama.cpp  -ncmoe 24            9936 MiB   55.52   (55.37 - 56.01)
llama.cpp  -ncmoe 28            8590 MiB   49.75   (49.55 - 49.98)
Ollama     automatic 44/56     10386 MiB   56.54   (56.33 - 56.84)
```

Realistic coding-agent shape — 8,117-token prompt, context 16384, prompt cache defeated on both sides:

```
config                         VRAM        prompt tok/s   gen tok/s
llama.cpp  -ncmoe 24           11100 MiB   901            48.72
Ollama     automatic 48/52     10424 MiB   850            46.25
```

By the pre-registered rule: at 4096, **+10.66%** with separated ranges — the challenger wins, by a hair over the line. At 16384 with a realistic prompt, **+5.3%** — no meaningful difference.

**But the comparison isn't like-for-like, and that's the actual finding.** At 4096 llama.cpp used 11,330 MiB against Ollama's 10,386 — 9% more VRAM for a 10.7% gain. Interpolating llama.cpp's own measured curve (9,936 MiB → 55.52; 11,330 MiB → 62.57; slope ~0.0051 tok/s per MiB) to Ollama's 10,386 MiB gives **~57.8 against Ollama's 56.54 — about +2%.**

The placement *algorithms* are within a couple of percent of each other. The measurable win is almost entirely that llama.cpp will spend VRAM Ollama leaves alone: Ollama stops near 10.4 GB of 12.0, llama.cpp at `-ncmoe 20` pushes to 11.3 and leaves ~950 MiB.

**On this machine that margin has a job.** The box drives three monitors and has a Steam library on the same disk as the models. The idle desktop alone holds ~457 MiB. Ollama's conservatism is correct behaviour for a workstation that is also an endpoint; llama.cpp's extra 6% is borrowed from the headroom that keeps the compositor from being evicted.

**Decision: stay on Ollama.** Revisit if this machine ever stops being a desktop.

**llama-swap: researched, declined.** v256 (2026-09-17), official images, and it genuinely does what `llama-server` can't — one OpenAI *and* Anthropic-compatible endpoint across N models, automatic eviction when two won't fit, and verbatim `llama-server` argv per model. That last one is the only thing Ollama can't match; Ollama exposes no `-ot` / `--n-cpu-moe` equivalent at all. But the condition for adopting it was "if llama.cpp wins," and it doesn't win at the context this machine works at. A second serving stack for ~2% isn't a trade worth making. Declined, not untried.

## What broke

**1. The benchmark measured the prompt cache instead of the model. Twice.** First attempt reported Ollama doing **286,957 tok/s** prompt processing — a cache hit, because the warm-up used the identical prompt. Second attempt appended a unique marker to defeat it and *still* produced 111,547 tok/s on one run, because a **trailing** nonce still matches a prefix cache. Moving the nonce to the front of the prompt produced a stable ~850 tok/s. Two plausible-looking wrong numbers before the measurement was real.

**2. An absurd number was the useful signal.** The first controlled run had llama.cpp at 127 tok/s prompt processing against Ollama's 2,043. Taken at face value that reverses the recommendation — prompt throughput dominates a coding-agent workload. It was an artifact of a 40-token prompt, where fixed overhead swamps the rate. Measured with an 8k prompt, both engines land near 900. **A number that would change the conclusion is worth re-measuring before believing**, in either direction.

**3. Two flag facts that the internet has wrong.**

- `--n-cpu-moe N` offloads the **first** N layers (`blk.0`..`blk.N-1`), not the highest-numbered ones. From `llm_add_n_cpu_ffn_overrides` in `common/common.h`: `for (int i = 0; i < n; ++i)` with ascending `blk.%d`. A widely-cited community MoE gist claims the reverse; it doesn't match master.
- `-ngl 99` **now disables llama.cpp's automatic memory fitter.** From a container log on this box, verbatim: `W common_fit_params: failed to fit params to free device memory: n_gpu_layers already set by user to 99, abort`. The old idiom is now counterproductive — omit `-ngl` and let `-fit` size it, or set both and accept manual control (which these runs did deliberately, for comparability).

`-ncmoe 20` is the exact floor at ctx 4096 on 12 GB; 19 dies with `unable to allocate CUDA0 buffer`. At ctx 16384 the floor is 24.

## What I would do differently

**Normalize the resource before comparing the result.** I nearly published "+10.7%, llama.cpp wins." The number is real and the conclusion it implies is wrong, because the two engines weren't spending the same VRAM. A speed comparison between two configurations that consume different amounts of the scarce resource is a comparison of the configurations, not the engines.

**Write the verdict rule before the numbers.** Having "|Δ| < 10% or overlapping ranges = no difference" fixed in advance is what made +5.3% report honestly as a non-result instead of getting written up as a win.

**Measure at the context you actually work at.** The 4096 result and the 16384 result point different directions. Only one of them describes this machine's real workload.

## Acceptance check

| | Check | Result |
|---|---|---|
| A3c.1 | Both engines run the identical weights file | pass — Ollama's own blob, mmap'd read-only, header verified |
| A3c.2 | Verdict rule fixed before numbers exist | pass |
| A3c.3 | Prompt cache defeated on both sides | pass — after two failures, ~850/~900 tok/s stable |
| A3c.4 | Sweep finds the load floor rather than guessing a setting | pass — `-ncmoe 19` fails, 20 is the floor at 4096, 24 at 16384 |
| A3c.5 | Result normalized for VRAM before a conclusion is drawn | pass — this is what changed the answer |
| A3c.6 | A decision is recorded either way | pass — stay on Ollama; llama-swap declined |

Phase closed. The automatic split was already about as good as the manual one; what looked like a 10% win was a VRAM budget being spent, and on this box that budget is the desktop's.
