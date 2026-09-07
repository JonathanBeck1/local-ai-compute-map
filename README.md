# Local AI compute, September 2026

Notes from ten days of looking for a product to build in personal AI compute orchestration. There isn't one — every layer already has something free in it. The notes were more useful than the idea, so here they are.

What each tool does, what it doesn't, dated. Checked 2026-09-03 to 2026-09-05.

[CORRECTIONS.md](CORRECTIONS.md) — seven things about this space that are wrong. Four were mine.
[VERIFY.md](VERIFY.md) — how to re-check any of it, how it was gathered, what that cost in errors.

## Local runtimes

All free. Pick on ergonomics.

| Tool | Does | Does **not** | Stars | Checked |
|---|---|---|---|---|
| [Ollama](https://github.com/ollama/ollama) | Local model runner. OpenAI-compatible and Anthropic `/v1/messages` endpoints (v0.14.0, 2026-01-10). Third-party gateway provider for Claude Desktop (v0.33.0, 2026-08-21). MIT. | Not a fleet manager. No scheduling across machines, no job cost estimate, no spend gate. Cloud tier went per-token on 2026-08-31 with credits and no hard cap. | 180,225 | 2026-09-05 |
| [LM Studio](https://lmstudio.ai/) | GUI runtime, MLX and GGUF. [LM Link](https://lmstudio.ai/link) connects your devices over an encrypted Tailscale mesh so one machine can use models loaded on another, served at `localhost:1234` so existing tools work unchanged. | LM Link is remote access, not scheduling. Its docs say you "load models on remote devices and use them as if they were local." No distribution or balancing. Free during preview only; LM Studio says there will be "both free as well as paid plans" at GA. Closed source. | n/a | 2026-09-05 |
| [llama.cpp](https://github.com/ggml-org/llama.cpp) | The engine most other things wrap. Metal and CUDA, every quantization that matters. MIT. | Not a service manager. Tagged 100 releases across 7 days when I checked (2026-09-05), so any published benchmark number has a short shelf life. | 127,144 | 2026-09-05 |
| [MLX](https://github.com/ml-explore/mlx) | Apple's array framework. Distributed support with tensor and pipeline parallelism; `mlx.distributed_config` finds the Thunderbolt topology, `mlx.launch` starts jobs over SSH. MIT. | Apple silicon only. Multi-Mac is CLI, hostfile and SSH. No registry, scheduler, failover or quotas. Built for researchers. | 28,312 | 2026-09-05 |
| [llama-swap](https://github.com/mostlygeek/llama-swap) | One binary, one YAML, hot-swaps models with TTL unload. MIT. | Single host. | 5,580 | 2026-09-05 |

## Across machines you own

This layer moved while I was writing about it.

| Tool | Does | Does **not** | Stars | Checked |
|---|---|---|---|---|
| [NVIDIA PAIR](https://github.com/NVIDIA/Personal-AI-Router) | Published 2026-09-03. Finds machines on your LAN, pairs with a six-digit PIN, sends each request to a free node. GeForce RTX 20-series and newer, RTX PRO, DGX Spark, and Apple M4+. Windows 11, Linux, macOS. Ollama and LM Studio. Apache-2.0. | From its README: "does not pool GPU memory, combine GPUs into a larger logical GPU, shard one model across machines, or split an in-flight inference request between nodes." Also "does not consider GPU model, available memory, model warmness, or how expensive a request looks." Inference only, LAN only, no budget concept. | 476 | 2026-09-05 |
| [exo](https://github.com/exo-explore/exo) | Actually shards models across devices. Two separate published results: a DGX Spark paired with an M3 Ultra runs Llama-3.1 8B (8,192-token prompt, 32-token generation) in 2.32s vs 6.42s for the M3 Ultra alone, a 2.8x gain, by giving prefill to the Spark (3.8x faster there) and generation to the Mac (3.4x faster there). Separately, on a cluster of M4 Pro 24 GB machines running LLaMA 3.2 3B, three devices serve 108.8 TPS against one device's 49.3, a 2.2x concurrency gain. Apache-2.0. | On that same M4 Pro cluster, *single-request* decode gets worse as you add nodes: 49.3 → 44.4 → 39.7 TPS at 1, 2 and 3 devices. You are buying capacity and concurrent throughput, not single-stream speed. No cost or policy layer. | 47,265 | 2026-09-05 |
| [GPUStack](https://github.com/gpustack/gpustack) | Cluster manager for NVIDIA, AMD and Ascend workers, automatic placement, OpenAI-compatible gateway. Apache-2.0. | No macOS workers since v2, which landed 2025-11-23. Models run in containers now and macOS won't hand a container the GPU. It is still the top answer in half the forum threads about mixed Mac and NVIDIA setups, nine months on. See [CORRECTIONS.md](CORRECTIONS.md). | 5,609 | 2026-09-05 |
| [LiteLLM](https://github.com/BerriAI/litellm) | Proxy with virtual keys, hard budgets per key or team or model, fallback chains, spend dashboards. | Governs API tokens. A budget here never sees a `sky launch`. | 58,097 | 2026-09-05 |
| [NeMo Switchyard](https://developer.nvidia.com/blog/route-ai-agent-workloads-across-models-with-nvidia-nemo-switchyard) | Routes each agent step to the best model by quality, latency and cost (2026-08-11). | Routes across models, not machines. Not the same problem as PAIR despite the similar pitch. | n/a | 2026-09-05 |

## Cloud

| Tool | Does | Does **not** | Stars | Checked |
|---|---|---|---|---|
| [SkyPilot](https://github.com/skypilot-org/skypilot) | Cross-cloud placement with an optimizer that prints $/hr per candidate before you launch. `--dryrun` exposes that to an agent. `resources.max_hourly_cost` shipped in v0.13.0 (2026-07-22). Admin Policies can reject or rewrite a launch. Apache-2.0, $20M seed 2026-07-21. | SSH node pools require a "Debian-based OS (tested on Debian 11)". No Macs as compute nodes. Estimates $/hr, never job duration. Admin Policies ship 16 examples and none of them is about cost, budget, spend or approval; the closest, RateLimitLaunchPolicy, limits request frequency rather than money. | 10,563 | 2026-09-05 |
| [dstack](https://github.com/dstackai/dstack) | Same shape as SkyPilot across clouds, Kubernetes and bare metal. Fleets take max-price and idle-duration. MPL-2.0. | Much less momentum. No Apple silicon story. | 2,237 | 2026-09-05 |
| [Brev Connect](https://docs.nvidia.com/brev/concepts/brev-connect) | Registers a Linux box you own into NVIDIA's console. NetBird mesh, NVML profiling, SSH, sharing. Free. | Linux only. Deliberately will not deploy workloads to registered machines. Inventory and connectivity, not orchestration. | n/a | 2026-09-05 |

## Fit and cost estimation

Least trustworthy section here. [CORRECTIONS.md](CORRECTIONS.md) entry 7 first.

| Tool | Does | Does **not** | Stars | Checked |
|---|---|---|---|---|
| [llmfit](https://github.com/AlexsJones/llmfit) | What runs on the machine in front of you, Apple-silicon unified memory included, with confidence labels. Ships an MCP server so an agent can ask it directly. MIT. | Inference only. No fine-tune time or cost. Fleet mode is an open PR. | 34,917 | 2026-09-05 |
| [Train-in-Silence](https://github.com/hlpun/Train-in-Silence) | Fine-tune VRAM, FLOPs, time and dollars across 14 providers, exposed to coding agents. | Its README: the estimation model is "fixed with no built-in calibration." No Apple silicon. No commits since 2026-08-04, zero issues ever filed. | 101 | 2026-09-05 |
| [MLX-LoRA-Studio](https://github.com/Goekdeniz-Guelmez/MLX-LoRA-Studio) | LoRA on Mac with a live memory estimate and a ResourceGuard. | No wall-clock or cost estimate. | 262 | 2026-09-05 |
| [LocalScore](https://github.com/cjpais/LocalScore) | Public database of standardized local benchmark results, opt-in. Apache-2.0. | Three fixed models (Llama 3.2 1B, Llama 3.1 8B, Qwen2.5 14B, all Q4_K), not your job or your quant. The site publishes no total result count, so claims about how much data it holds — including one I made earlier — are not checkable from the outside. | 128 | 2026-09-05 |

## Stopping an agent from spending your money

Already exists. Not a third-party product.

- [Hooks](https://code.claude.com/docs/en/hooks) — `PreToolUse` returns `allow`/`deny`/`ask`/`defer`, matches on command pattern, and an `ask` prompts even in auto mode. Knows nothing about dollars. The cost logic is yours: ~60 lines around `sky launch --dryrun`.
- [Permission modes](https://code.claude.com/docs/en/permission-modes) — auto mode default since 2026-08-14; classifier blocked 89% of dangerous commands vs 13.6% for humans over 1,053 cases. Block list covers production deploys, IAM grants, shared infrastructure, protected IaC, force push, destructive git. No spend, billing, budget or purchase criterion anywhere in it.
- Perplexity Portable Computer — per-step approval before cloud escalation, PII classifier over what leaves. DGX Spark or Linux + RTX ≥24 GB. Hybrid Compute does the same on Apple silicon since 2026-09-01, 24 GB minimum. Subscription.
- LM Studio Bionic — reviews shell commands before running (1.1.0, 2026-08-27).

Agent-initiated cloud spend is the one thing on this page nothing gates.

## Hardware

Decode speed tracks bandwidth over active bytes per token. Not FLOPS, not capacity.

| Machine | Memory | Bandwidth | Price |
|---|---|---|---|
| Mac Studio M5 Ultra | up to 512 GB unified | 1.2 TB/s | from $5,499, 512 GB config late Oct 2026 |
| RTX 4070 | 12 GB | 504 GB/s | consumer |
| DGX Spark | 128 GB unified | 273 GB/s | ~$4,699 (not listed on NVIDIA's spec page; sold via their marketplace) |
| AMD Strix Halo | 128 GB LPDDR5X | — | ~$2,000–3,500, varies by builder (unverified) |

The 4070 out-decodes the Spark on anything that fits in 12 GB, with a tenth of the memory. Buy the Spark for capacity and CUDA, not speed. Capacity and speed are separate purchases.

## If you own

**A Mac and a gaming PC.** PAIR and LM Link both come up here and they are not substitutes. PAIR spreads requests across both machines; you want it when work queues up. LM Link lets the laptop use a model loaded on the desktop; you want it when one machine has the VRAM and the other has your keyboard. Both free, both about an evening. Not GPUStack, it dropped macOS.

**One machine, and you want to know what fits.** llmfit, and stop reading calculator sites. It ships an MCP server, so your coding agent can just ask it.

**An occasional rented GPU.** SkyPilot. `--dryrun` prints the per-candidate cost before you commit, `resources.max_hourly_cost` caps it. If an agent is doing the launching, write the hook, because nothing in the classifier counts dollars.

**An idea for a knowledge graph that predicts placement across everyone's hardware.** Don't. Count the cells: models times quantizations times runtimes times GPU SKUs times context lengths, and every one of them goes stale as runtimes ship — llama.cpp alone tagged 100 releases across 7 days when I checked. No public benchmark commons collects anywhere near enough to keep up, and the ones that exist pin themselves to three fixed models precisely because the full space is not coverable.

## Build log

[`build-log/`](build-log/) — same thing on real hardware. Two Macs, a 12 GB CUDA box, a NAS, rented GPUs when something won't fit. Output pasted in, failures left where they happened.

Empty until I've run them.

## Corrections

Open an issue: the claim, a primary source, the date you checked. Corrections to my own errors are the useful kind.

Requests to turn this into a tool get declined.
