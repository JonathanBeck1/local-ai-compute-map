# Local AI compute, September 2026

What the tools for running AI on your own hardware actually do, and what they don't. Every row has a
date. [VERIFY.md](VERIFY.md) shows how to re-check any of it. [CORRECTIONS.md](CORRECTIONS.md) lists
seven claims about this space that are wrong, including four I had wrong myself.

Star counts and licenses checked 2026-09-05. Feature claims checked 2026-09-03 to 2026-09-05.

Written with heavy use of an AI coding agent. Method and its limits: [VERIFY.md](VERIFY.md#method).

## Why this exists

I spent about ten days working out whether there was a product to build in personal AI compute
orchestration. There isn't. Every layer already has a free first-party occupant.

Runtimes: Ollama, LM Studio, llama.cpp, MLX. Cloud: SkyPilot. Fit estimation: llmfit. Cross-machine
routing was the last open gap, and NVIDIA closed it on 2026-09-03 with PAIR, which routes to Macs.

The survey I did on the way turned out to be worth more than the product idea, mostly because the
guides I was reading were stale. So this is the survey.

There is no tool here. No install, no CLI, no config. If you came looking for a control plane for a
mixed Mac and NVIDIA setup, the answer is that the free options below cover it.

## Local runtimes

Where the model runs. All free, differences are ergonomic.

| Tool | Does | Does **not** | Stars | Checked |
|---|---|---|---|---|
| [Ollama](https://github.com/ollama/ollama) | Local model runner. OpenAI-compatible and Anthropic `/v1/messages` endpoints (v0.14.0, 2026-01-10). Third-party gateway provider for Claude Desktop (v0.33.0, 2026-08-21). MIT. | Not a fleet manager. No scheduling across machines, no job cost estimate, no spend gate. Cloud tier went per-token on 2026-08-31 with credits and no hard cap. | 180,225 | 2026-09-05 |
| [LM Studio](https://lmstudio.ai/) | GUI runtime, MLX and GGUF. [LM Link](https://lmstudio.ai/link) connects your devices over an encrypted Tailscale mesh so one machine can use models loaded on another, served at `localhost:1234` so existing tools work unchanged. | LM Link is remote access, not scheduling. Its docs say you "load models on remote devices and use them as if they were local." No distribution or balancing. Free during preview only; LM Studio says there will be "both free as well as paid plans" at GA. Closed source. | n/a | 2026-09-05 |
| [llama.cpp](https://github.com/ggml-org/llama.cpp) | The engine most other things wrap. Metal and CUDA, every quantization that matters. MIT. | Not a service manager. Ships about a dozen tagged builds a day, so published benchmark numbers go stale fast. | 127,144 | 2026-09-05 |
| [MLX](https://github.com/ml-explore/mlx) | Apple's array framework. Distributed support with tensor and pipeline parallelism; `mlx.distributed_config` finds the Thunderbolt topology, `mlx.launch` starts jobs over SSH. MIT. | Apple silicon only. Multi-Mac is CLI, hostfile and SSH. No registry, scheduler, failover or quotas. Built for researchers. | 28,312 | 2026-09-05 |
| [llama-swap](https://github.com/mostlygeek/llama-swap) | One binary, one YAML, hot-swaps models with TTL unload. MIT. | Single host. | 5,580 | 2026-09-05 |

## Across machines you own

The layer that changed most recently, and it changed against building anything.

| Tool | Does | Does **not** | Stars | Checked |
|---|---|---|---|---|
| [NVIDIA PAIR](https://github.com/NVIDIA/Personal-AI-Router) | Published 2026-09-03. Finds machines on your LAN, pairs with a six-digit PIN, sends each request to a free node. GeForce RTX 20-series and newer, RTX PRO, DGX Spark, and Apple M4+. Windows 11, Linux, macOS. Ollama and LM Studio. Apache-2.0. | From its README: "does not pool GPU memory, combine GPUs into a larger logical GPU, shard one model across machines, or split an in-flight inference request between nodes." Also "does not consider GPU model, available memory, model warmness, or how expensive a request looks." Inference only, LAN only, no budget concept. | 476 | 2026-09-05 |
| [exo](https://github.com/exo-explore/exo) | Actually shards models across devices, including a Mac and a DGX Spark together. Reports 2.8x on that pairing and 2.2x under concurrency. Apache-2.0. | Single-request decode gets worse with more nodes, not better: their own figure is 49.3 → 39.7 tok/s from 1 to 3. You are buying capacity and concurrency, not speed. No cost or policy layer. | 47,265 | 2026-09-05 |
| [GPUStack](https://github.com/gpustack/gpustack) | Cluster manager for NVIDIA, AMD and Ascend workers, automatic placement, OpenAI-compatible gateway. Apache-2.0. | No macOS workers since v2 (2025-11-23). Models run in containers and macOS won't give a container GPU access. Still recommended everywhere as the Mac plus NVIDIA answer. See [CORRECTIONS.md](CORRECTIONS.md). | 5,609 | 2026-09-05 |
| [LiteLLM](https://github.com/BerriAI/litellm) | Proxy with virtual keys, hard budgets per key or team or model, fallback chains, spend dashboards. | Governs API tokens. A budget here never sees a `sky launch`. | 58,097 | 2026-09-05 |
| [NeMo Switchyard](https://developer.nvidia.com/blog/route-ai-agent-workloads-across-models-with-nvidia-nemo-switchyard) | Routes each agent step to the best model by quality, latency and cost (2026-08-11). | Routes across models, not machines. Not the same problem as PAIR despite the similar pitch. | n/a | 2026-09-05 |

## Cloud

| Tool | Does | Does **not** | Stars | Checked |
|---|---|---|---|---|
| [SkyPilot](https://github.com/skypilot-org/skypilot) | Cross-cloud placement with an optimizer that prints $/hr per candidate before you launch. `--dryrun` exposes that to an agent. `resources.max_hourly_cost` shipped in v0.13.0 (2026-07-22). Admin Policies can reject or rewrite a launch. Apache-2.0, $20M seed 2026-07-21. | SSH node pools require a "Debian-based OS (tested on Debian 11)". No Macs as compute nodes. Estimates $/hr, never job duration. Admin Policies ship 13 examples and none of them is about cost or approval. | 10,563 | 2026-09-05 |
| [dstack](https://github.com/dstackai/dstack) | Same shape as SkyPilot across clouds, Kubernetes and bare metal. Fleets take max-price and idle-duration. MPL-2.0. | Much less momentum. No Apple silicon story. | 2,237 | 2026-09-05 |
| [Brev Connect](https://docs.nvidia.com/brev/concepts/brev-connect) | Registers a Linux box you own into NVIDIA's console. NetBird mesh, NVML profiling, SSH, sharing. Free. | Linux only. Deliberately will not deploy workloads to registered machines. Inventory and connectivity, not orchestration. | n/a | 2026-09-05 |

## Fit and cost estimation

Crowded, and the least reliable category here. Read [CORRECTIONS.md](CORRECTIONS.md) entry 7 first.

| Tool | Does | Does **not** | Stars | Checked |
|---|---|---|---|---|
| [llmfit](https://github.com/AlexsJones/llmfit) | What runs on the machine in front of you, Apple-silicon unified memory included, with confidence labels. Ships an MCP server so an agent can ask it directly. MIT. | Inference only. No fine-tune time or cost. Fleet mode is an open PR. | 34,917 | 2026-09-05 |
| [Train-in-Silence](https://github.com/hlpun/Train-in-Silence) | Fine-tune VRAM, FLOPs, time and dollars across 14 providers, exposed to coding agents. | Its README: the estimation model is "fixed with no built-in calibration." No Apple silicon. No commits since 2026-08-04, zero issues ever filed. | 101 | 2026-09-05 |
| [MLX-LoRA-Studio](https://github.com/Goekdeniz-Guelmez/MLX-LoRA-Studio) | LoRA on Mac with a live memory estimate and a ResourceGuard. | No wall-clock or cost estimate. | 262 | 2026-09-05 |
| [LocalScore](https://github.com/cjpais/LocalScore) | Public database of standardized local benchmark results, opt-in. Apache-2.0. | Fixed models, not your job. About 4,100 results in 17 months, which is far too sparse to predict an arbitrary model and quant and runtime and GPU combination. | 128 | 2026-09-05 |

## Stopping an agent from spending your money

This layer exists already, and it isn't a third-party product.

[Claude Code hooks](https://code.claude.com/docs/en/hooks): a `PreToolUse` hook returns
`allow`/`deny`/`ask`/`defer` and can match on a command pattern. An `ask` forces a prompt even in auto
mode. Nothing in it knows about dollars, so the cost logic is yours to write, roughly 60 lines around
`sky launch --dryrun`.

[Permission modes](https://code.claude.com/docs/en/permission-modes): auto mode has been the default
since 2026-08-14. In a 1,053-case study the classifier blocked 89% of dangerous commands against 13.6%
for the humans. Its criteria cover shared infrastructure and autonomous loops, but there is no spend,
billing, budget or purchase criterion anywhere in them. Agent-initiated cloud spend is the one thing
here that is genuinely still ungated.

Perplexity Portable Computer asks before any step escalates to a cloud model and runs a PII classifier
over what leaves. Hybrid Compute does the same on Apple silicon since 2026-09-01, 24 GB minimum.
Subscription product; Portable Computer needs a DGX Spark or a Linux box with an RTX 24 GB or better.

LM Studio's Bionic agent reviews shell commands before running them (1.1.0, 2026-08-27).

## Hardware

Decode speed on a memory-bound setup tracks memory bandwidth divided by active bytes per token. Not
FLOPS, not capacity. A small card with fast memory beats a big box with slow memory on any model that
fits in both.

| Machine | Memory | Bandwidth | Price |
|---|---|---|---|
| Mac Studio M5 Ultra | up to 512 GB unified | 1.2 TB/s | from $5,499, 512 GB config late Oct 2026 |
| RTX 4070 | 12 GB | 504 GB/s | consumer |
| DGX Spark | 128 GB unified | 273 GB/s | $4,699, up from $3,999 on 2026-02-23 |
| AMD Strix Halo | 128 GB LPDDR5X | — | ~$2,000–3,500 |

The 4070 beats the Spark on decode for anything that fits in 12 GB. Buy the Spark for CUDA
compatibility and capacity, not speed. Capacity and speed are separate purchases and neither is an
upgrade over the other.

## If you own

**A Mac and a gaming PC.** These two are not substitutes, so pick by problem. PAIR distributes
requests across both machines, which is what you want when work queues up. LM Link lets the laptop use
a model loaded on the desktop, which is what you want when one machine has the VRAM and the other has
your keyboard. Both free, both an evening. Don't use GPUStack, it dropped macOS.

**One machine.** llmfit. It has an MCP server so your agent can ask it directly.

**An occasional rented GPU.** SkyPilot with `--dryrun` for the per-candidate cost, and
`resources.max_hourly_cost` as a ceiling. If an agent is doing the launching, add a `PreToolUse` hook,
because the classifier doesn't count dollars.

**An idea for a knowledge graph that predicts placement across everyone's hardware.** Don't. It's
roughly a million meaningful cells that go stale in days as runtimes ship, and the best-instrumented
public effort in this niche collects a few hundred observations a month.

## Build log

[`build-log/`](build-log/) is the same setup on real hardware: two Macs, a 12 GB CUDA box, a NAS,
occasional rented GPUs. One entry per phase with pasted output, what broke, what it cost.

Empty until the phases actually run.

## Corrections

Open an issue with the claim, a primary source, and your check date. Details at the end of
[CORRECTIONS.md](CORRECTIONS.md).

Requests to turn this into a tool will be declined.
