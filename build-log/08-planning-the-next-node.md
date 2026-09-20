# Phase 08 — Planning the next node, and what "one model, many agents" actually costs

**Status:** research and measurement done; no hardware bought yet
**Date:** 2026-09-20
**Elapsed:** ~2 h
**Cost:** $0 (the point of measuring first)

## Goal

The workstation works. The next question is what to add, and the appealing
answer is "one machine big enough to hold one excellent coding model, with
several agents pointed at it." Before spending four figures on that sentence,
three things needed checking: whether NVIDIA's PAIR pools memory across machines
(no), what the candidate machines actually do (less than advertised), and
whether one loaded model can serve several agents at all (it depends, and the
failure is silent).

## PAIR routes requests; it does not pool memory

[PAIR](https://github.com/NVIDIA/Personal-AI-Router) is NVIDIA's local inference
router, and the appeal for a small lab is obvious: several machines, one
endpoint. Its own documentation is blunt about the limit:

> "PAIR routes each independent request to one node. It does **not** pool GPU
> memory, combine GPUs into a larger logical GPU, shard one model across
> machines, or split an in-flight inference request between nodes."

So two 16 GB Macs do not become a 32 GB machine. **The largest model you can run
is still whatever your largest single node holds.** What PAIR buys is
parallelism across *independent* requests — NVIDIA's own example runs a
five-subagent workload in 8m48s across three devices against 18m on one.

Eligibility is narrower than it first looks: GeForce RTX 20-series and newer,
RTX PRO (Turing+), DGX Spark, and **Apple M4 or newer**. Against this lab:

| Machine | Eligible |
|---|---|
| Workstation, RTX 4070 | yes |
| NAS, RTX 2060 Super | yes — 20-series makes the cut |
| Mac mini M4 | yes |
| MacBook Pro **M3** Pro | **no** — below the M4 floor |

## The candidate machines, with the marketing removed

Two obvious options: an NVIDIA DGX Spark (128 GB unified, ~273 GB/s, $4,699) or
an Apple M5 Ultra Mac Studio (96–512 GB unified, 1.2 TB/s, from $5,499).

**The M5 Ultra benchmark tables circulating online are not measurements.** The
machine ships 2026-09-22; the tables predate it. They also fail arithmetic.
Dense decode must read every weight once per token, so tokens/sec × bytes/token
cannot exceed memory bandwidth — and most published rows do:

```
model                   GB/tok   claimed  GB/s needed  verdict
Qwen2.5 14B 4-bit          7.9      130/s        1024  plausible (85% of bandwidth)
Qwen2.5 32B 4-bit         18.0       78/s        1404  IMPOSSIBLE - 117% of bandwidth
Llama 3.3 70B 4-bit       39.4       47/s        1851  IMPOSSIBLE - 154%
Llama 3.3 70B 8-bit       74.2       27/s        2003  IMPOSSIBLE - 167%
Mistral 24B 8-bit         25.4       71/s        1806  IMPOSSIBLE - 151%
Mixtral 8x22B 4-bit       21.9       32/s         702  plausible (58%)
Llama 3.1 405B 4-bit     227.8       10/s        2278  IMPOSSIBLE - 190%
```

One row is self-refuting without any arithmetic: 405B at 4-bit is **228 GB of
weights**, and the article says it was tested on a **192 GB** machine.

The two rows that *do* pass are the small dense model and **the MoE** — the same
pattern [03](03-local-model-endpoint.md) measured here.

For an honest estimate, calibrate on hardware that exists. From llama.cpp's
[community table](https://github.com/ggml-org/llama.cpp/discussions/4167):

```
M2 Ultra 7B Q8_0   7.2 GB/tok x 66.6 tok/s = 480 GB/s = 60% of peak
M3 Ultra 7B Q8_0   7.2 GB/tok x 63.9 tok/s = 460 GB/s = 58% of peak
```

Apple sustains ~58–60% of peak on bandwidth-bound decode. Scaling that to
1.2 TB/s gives **~18–21 tok/s on a dense 70B at 4-bit**, not the advertised
42–52. Still roughly 4× a Spark — just half the claim.

Measured Spark numbers, meanwhile, are published and consistent with its 273 GB/s:

```
dense Llama 3.1 70B      2.7 tok/s decode |  803 tok/s prefill
GPT-OSS-120B (MoE, ~5B)  60.6 tok/s decode | 1956 tok/s prefill
```

**A 22× spread from architecture alone on one machine.** Same rule, different
silicon: total parameters set what fits, active parameters set how fast it runs.

Worth stating for scale: this workstation does **41.6 tok/s** on an 80B-A3B —
69% of a $4,699 Spark's MoE decode rate, on hardware already owned. The gap is
prefill (678 vs 1,956 tok/s), which is the compute-bound half.

## The question the purchase actually turns on

"One model, many agents" is a concurrency claim, and it is testable on hardware
already here. Method: warm the model, then fire N identical requests
concurrently, N = 1, 2, 4, 8, with `OLLAMA_NUM_PARALLEL=8` set explicitly so the
test measures the hardware rather than the runtime's guess. Record what each
agent experiences and what the box delivers in total.
Script: [`scripts/concurrency.py`](scripts/concurrency.py).

```
model                 residency  slots   solo    at 8 agents   aggregate  scaling
gemma4:12b (dense)    100% VRAM    8    53.5 t/s  30.6 t/s each  234 t/s    4.4x
qwen3-coder:30b (MoE)  ~50% VRAM   8    45.2 t/s  23.8 t/s each  134 t/s    3.0x
qwen3-next-80b (MoE)    23% VRAM   1    41.3 t/s  40.8 t/s each   39 t/s    1.0x
```

**The last row is the finding.** The 80B got `n_seq_max = 1`. Ollama ignored
`OLLAMA_NUM_PARALLEL=8` and served every "concurrent" request strictly one at a
time — wall time scaled linearly with agent count, 13.1 s for four and 26.1 s
for eight.

**And it fails in the direction that fools you.** Per-agent throughput looked
*healthy* at 40.8 tok/s — better than the 30 tok/s the dense model gave under
real load. Reading only that number, the box looks like it is serving eight
agents well. It is serving one agent eight times. The tell is that aggregate
equals per-agent, which only happens when nothing overlaps.

**Slots are a memory decision, not a setting.** The 30B spills too and still got
eight slots; only when the model grew large enough relative to free memory did
the runtime silently collapse to one. Nothing logged a warning at the API level.

Honest limitation: this cannot cleanly separate "MoE" from "spilling", because
every MoE on this machine spills. The dense 4.4× against MoE 3.0× is suggestive,
not established.

## What that means for the machine being considered

The target model is **DeepSeek-V4-Flash**: 284B total, **13B active**, 1M
context, and 155 GB at Q4 with ~172 GB recommended once speculative decoding is
enabled. That number is why 256 GB is the right tier and 128 GB is not — a Spark
or a 96 GB Studio has to drop to 3-bit. It is also why 512 GB is not required:
the larger DeepSeek-V4-Pro is 1.6T parameters, unreachable on any Mac, and the
744B alternatives have 3× the active parameters and would decode *slower*.

Budget on a 256 GB machine, with the wired limit raised from its 75% default:

```
model + draft   ~172 GB
macOS            ~16 GB
left for KV      ~58 GB   -> the agent count, whatever that divides into
```

Because the model is resident rather than spilling, it should batch like the
gemma4 row, not the 80B row. **Should. That is a prediction, and phase 08 is
where it gets written down so the machine can falsify it.**

## Acceptance check

| | Check | Result |
|---|---|---|
| A8.1 | Establish whether PAIR pools memory | pass — it does not; documented, with eligibility mapped to this lab |
| A8.2 | Candidate performance from measurements, not vendor claims | pass — Spark measured; Apple scaled from real M2/M3 Ultra runs |
| A8.3 | Published M5 Ultra benchmarks checked against physics | pass — 5 of 7 rows exceed memory bandwidth; one exceeds the tested machine's RAM |
| A8.4 | Concurrency measured on real hardware | pass — 3 models, N=1..8, aggregate and per-agent |
| A8.5 | The silent-failure mode identified | pass — `n_seq_max=1` while per-agent throughput looks healthy |
| A8.6 | A test that transfers to the new machine | pass — same script, plus "check `n_seq_max` before believing any number" |

Nothing bought yet. The next entry is either the purchase and its acceptance
run, or the network rebuild that has to precede PAIR either way.
