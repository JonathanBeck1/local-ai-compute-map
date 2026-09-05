# Local AI compute, September 2026: what's actually alive

A dated, primary-sourced map of the tools people use to run and orchestrate AI on hardware they own —
Apple silicon, consumer NVIDIA, small home fleets, and rented GPUs — with a column most guides leave
out: **what each tool does not do.**

Every row carries the date I last checked it. Nothing here is taken from a comparison article. See
[VERIFY.md](VERIFY.md) for how to re-check any of it yourself, and [CORRECTIONS.md](CORRECTIONS.md)
for six widely-repeated claims in this space that are false — three of which were my own errors
before they were anyone else's.

**Star counts and licenses verified 2026-09-05. Feature and limitation claims verified 2026-09-03 to
2026-09-05.**

---

## What this is, and what it is not

This **is** a survey and a build log. It came out of about ten days of adversarial research into
whether there was a product to build in this space. The conclusion was no, and the write-up of why is
not public. What is public is the part that turned out to be worth more than the product idea: an
inventory of what actually exists, checked against primary sources, on a specific date.

This is **not** a tool. There is no package to install, no CLI, no daemon, no config schema for your
fleet. If you want a control plane for heterogeneous personal compute, the honest answer as of today
is that the free first-party options below cover most of it and the remaining gap is not worth a
weekend. That conclusion is the single most useful thing in this repo.

---

## The shape of the landscape in one paragraph

Every layer of the personal AI compute stack now has a free, first-party occupant, and most of them
arrived in the last twelve months. Runtimes are free and excellent (Ollama, LM Studio, llama.cpp,
MLX). Fleet routing across machines you own went from a hobbyist gap to a vendor feature in one week:
NVIDIA published PAIR on 2026-09-03, routing across RTX, DGX Spark, **and Apple silicon** on your LAN,
and LM Studio's LM Link, with Tailscale, already let one machine use models loaded on another. Cloud orchestration
is owned by SkyPilot, which now has $20M and a pre-launch cost optimizer. Fit estimation is owned by
llmfit. Approval gates for agent actions are a feature of the coding agents themselves. The
interesting remaining questions in this space are not "what should someone build" — they are "how
fast is this actually on my hardware" and "what is my agent authorized to spend," and both are
measurement problems, not software problems.

---

## Local runtimes

Where the model actually executes. All free, all good, differences are ergonomic.

| Tool | What it does | What it does **not** do | Stars | Checked |
|---|---|---|---|---|
| [Ollama](https://github.com/ollama/ollama) | Local model runner, one-command pulls, OpenAI-compatible and Anthropic `/v1/messages` endpoints (v0.14.0, 2026-01-10). Acts as a third-party gateway provider for Claude Desktop (v0.33.0, 2026-08-21). MIT. | Not a fleet manager. Does not schedule across machines, estimate job cost, or gate spend. Cloud tier moved to per-token pricing 2026-08-31 with credits and no hard cap. | 180,225 | 2026-09-05 |
| [LM Studio](https://lmstudio.ai/) | GUI runtime, MLX and GGUF, plus **[LM Link](https://lmstudio.ai/link)** — connects devices you own over an end-to-end encrypted Tailscale mesh so one machine can load and use models running on another; remote models appear at the standard `localhost:1234` endpoint, so existing tools work unchanged. Bionic agent adds Auto Review for shell commands (1.1.0, 2026-08-27). | LM Link is **remote access, not scheduling** — its own docs say it lets you "load models on remote devices and use them as if they were local," not distribute or balance work across them. Free **during preview only**: LM Studio states there will be "both free as well as paid plans once the feature is released for General Availability." No device limit stated either way. Closed source. Raised $19.32M — not bootstrapped, contrary to common belief. | n/a | 2026-09-05 |
| [llama.cpp](https://github.com/ggml-org/llama.cpp) | The engine most other things wrap. CPU and GPU, every quantization format that matters, Metal and CUDA. MIT. | Not a service manager or a fleet tool. Ships very fast — roughly a dozen tagged builds a day — so any performance number you read about it has a short shelf life. | 127,144 | 2026-09-05 |
| [MLX](https://github.com/ml-explore/mlx) | Apple's array framework for Apple silicon. Distributed support: tensor and pipeline parallelism, `mlx.distributed_config` auto-discovers Thunderbolt topology, `mlx.launch` starts jobs over SSH. MIT. | Apple silicon only. The multi-Mac story is CLI, hostfile, and SSH — no registry, scheduler, failover, or quotas. Aimed at researchers, not operators. | 28,312 | 2026-09-05 |
| [llama-swap](https://github.com/mostlygeek/llama-swap) | One binary, one YAML. Fronts llama.cpp/vLLM and hot-swaps models on demand with TTL unload. MIT. | Single host. No multi-machine placement, no cost awareness. | 5,580 | 2026-09-05 |

## Fleet and routing across machines you own

This is the layer that changed most recently, and the change went against building anything yourself.

| Tool | What it does | What it does **not** do | Stars | Checked |
|---|---|---|---|---|
| [NVIDIA PAIR](https://github.com/NVIDIA/Personal-AI-Router) | Published **2026-09-03**. Apache-2.0. Discovers machines on your LAN, pairs with a six-digit PIN, routes each inference request to one eligible node. Supports GeForce RTX 20-series and newer, RTX PRO, DGX Spark, **and Apple M4+ silicon**, on Windows 11, Linux, macOS. Works with Ollama and LM Studio. | Its own README: "does not pool GPU memory, combine GPUs into a larger logical GPU, shard one model across machines, or split an in-flight inference request between nodes" and "does not consider GPU model, available memory, model warmness, or how expensive a request looks." Inference only, LAN only, no cloud nodes, no budget concept. | 476 | 2026-09-05 |
| [exo](https://github.com/exo-explore/exo) | Heterogeneous local clustering that genuinely shards models across devices, including Mac + DGX Spark together. Apache-2.0. Published measurements: 2.8x on heterogeneous DGX Spark + M3 Ultra; 2.2x under concurrency. | Single-request decode does not scale linearly — their own figure is 49.3 → 39.7 tok/s going from 1 to 3 nodes. Sharding buys capacity and concurrency, not single-stream speed. No cost or policy layer. | 47,265 | 2026-09-05 |
| [GPUStack](https://github.com/gpustack/gpustack) | Cluster manager for NVIDIA/AMD/Ascend workers with automatic placement and an OpenAI-compatible gateway. Apache-2.0. | **No macOS workers since v2** (2025-11-23) — everything runs in containers and macOS does not allow GPU access from containers. Still widely and wrongly recommended as the Mac + NVIDIA answer. See [CORRECTIONS.md](CORRECTIONS.md). | 5,609 | 2026-09-05 |
| [LiteLLM](https://github.com/BerriAI/litellm) | Proxy with virtual keys, hard budgets per key/team/model with resets, fallback chains local → cloud, spend dashboards. | Governs **API tokens**, not machines or GPU rentals. A budget here never sees a `sky launch`. | 58,097 | 2026-09-05 |
| [NeMo Switchyard](https://developer.nvidia.com/blog/route-ai-agent-workloads-across-models-with-nvidia-nemo-switchyard) | Open-source routing of each agent step to the best model by quality/latency/cost (2026-08-11). | Routes across **models**, not across **machines**. Different problem from PAIR despite similar framing. | n/a | 2026-09-05 |

## Cloud orchestration and burst

| Tool | What it does | What it does **not** do | Stars | Checked |
|---|---|---|---|---|
| [SkyPilot](https://github.com/skypilot-org/skypilot) | Cross-cloud placement with a cost optimizer that prints $/hr per candidate before launch. `--dryrun` exposes it to agents. `resources.max_hourly_cost` shipped in v0.13.0 (2026-07-22). Admin Policies can reject or mutate launches. Apache-2.0, $20M seed 2026-07-21. | SSH node pools are **Debian-based Linux only** — no Macs as compute nodes. Estimates $/hr, not job duration. Admin Policies ship 13 examples, **none** for cost or approval. Its Agent Skill never mentions budgets. | 10,563 | 2026-09-05 |
| [dstack](https://github.com/dstackai/dstack) | Vendor-agnostic orchestration across clouds, Kubernetes, and bare metal; fleets with max-price and idle-duration. MPL-2.0. | Same shape as SkyPilot with far less momentum. No Apple silicon compute story. | 2,237 | 2026-09-05 |
| [NVIDIA Brev Connect](https://docs.nvidia.com/brev/concepts/brev-connect) | Registers a Linux machine you own into NVIDIA's console: NetBird mesh, NVML hardware profiling, SSH, sharing. Free. | **Linux only.** Deliberately does not deploy workloads to registered machines — it is connectivity and inventory, not orchestration. | n/a | 2026-09-05 |

## Fit and cost estimation

The most crowded and least reliable category. Read [CORRECTIONS.md](CORRECTIONS.md) entry 6 first.

| Tool | What it does | What it does **not** do | Stars | Checked |
|---|---|---|---|---|
| [llmfit](https://github.com/AlexsJones/llmfit) | The category winner. What runs on the box in front of you, including Apple-silicon unified memory, with hardware profiles and confidence labels. **Ships its own MCP server**, so agents can query it directly. MIT. | Inference only — no fine-tune time or cost. Cross-machine fleet mode is an open PR, not a feature. | 34,917 | 2026-09-05 |
| [Train-in-Silence](https://github.com/hlpun/Train-in-Silence) | Fine-tune VRAM/FLOPs/time/$ across 14 providers, exposed to coding agents. | Its own README: the estimation model is fixed with **no built-in calibration**. No Apple silicon. No pushes since 2026-08-04, zero issues ever filed. | 101 | 2026-09-05 |
| [MLX-LoRA-Studio](https://github.com/Goekdeniz-Guelmez/MLX-LoRA-Studio) | LoRA fine-tuning on Mac with a live memory estimate and a ResourceGuard. | No wall-clock time or cost estimate. Mac only. | 262 | 2026-09-05 |
| [LocalScore](https://github.com/cjpais/LocalScore) | Opt-in public database of standardized local benchmark results. Apache-2.0. | Fixed benchmark models, not your job. Accumulated roughly 4,100 results in 17 months — useful, but far too sparse to predict an arbitrary model/quant/runtime/hardware combination. | 128 | 2026-09-05 |
| Web VRAM calculators | Fine for the fit question: does it fit in memory. | Silent or wrong on the speed question. See below. | — | 2026-09-05 |

## Agent-side controls

If your concern is an agent spending money or touching infrastructure, this is the layer that already
exists — and it is not a third-party product.

| Control | What it does | What it does **not** do | Checked |
|---|---|---|---|
| [Claude Code hooks](https://code.claude.com/docs/en/hooks) | A `PreToolUse` hook returns `allow`/`deny`/`ask`/`defer` and can filter on a command pattern. A hook's `ask` forces a prompt even in auto mode. | Nothing about dollars. You write the cost logic yourself; it is roughly 60 lines around `sky launch --dryrun`. | 2026-09-05 |
| [Claude Code permission modes](https://code.claude.com/docs/en/permission-modes) | Auto mode has been the default since 2026-08-14, with a classifier catching 89% of dangerous commands versus 13.6% for humans in the same test. Explicit ask rules still force a prompt. | The classifier's criteria include shared infrastructure and autonomous agent loops but contain **no spend, billing, budget, or purchase criterion.** Tool-initiated cloud spend is the one genuinely ungated seam. | 2026-09-05 |
| Perplexity Portable Computer / Hybrid Compute | Per-step approval before any step escalates to a cloud model, with a PII classifier over outgoing context. Hybrid Compute on Apple silicon since 2026-09-01, 24 GB minimum. | Subscription product. Portable Computer needs a DGX Spark or a Linux box with an RTX ≥24 GB. | 2026-09-05 |
| LM Studio Bionic Auto Review | Reviews shell commands before execution (1.1.0, 2026-08-27). | Local tool execution only. | 2026-09-05 |

---

## Hardware: the number that actually predicts speed

For local inference on a memory-bound setup, decode speed tracks **memory bandwidth divided by active
bytes per token**, not headline FLOPS and not capacity. This is why a small fast-memory GPU beats a
large slow-memory box on a model that fits in both.

| Machine | Memory | Bandwidth | Price | Note |
|---|---|---|---|---|
| Mac Studio M5 Ultra | up to 512 GB unified | 1.2 TB/s | from $5,499; 512 GB config late Oct 2026 | Announced 2026-08-25. Capacity leader. 512 GB configs land well above the base price. |
| RTX 4070 | 12 GB VRAM | 504 GB/s | consumer | Beats a DGX Spark on decode for any model that fits in 12 GB. |
| DGX Spark | 128 GB unified | 273 GB/s | $4,699 | Price rose from $3,999 on 2026-02-23. Buy it for CUDA compatibility and capacity, not speed. |
| AMD Strix Halo | 128 GB LPDDR5X | — | ~$2,000–3,500 mini-PCs | Strong on MoE models where active parameters are small. |

The practical consequence: capacity and speed are separate purchases. A 128 GB box that runs a large
model slowly and a 12 GB card that runs a small model quickly solve different problems, and neither
is an upgrade over the other.

---

## If you own X, do Y

The short version, for the three common cases.

**A Mac and a gaming PC, and you want them to work together.** Pick by which problem you have, because
these two tools are not substitutes. **NVIDIA PAIR** distributes requests: it discovers both machines
and sends each inference request to whichever node is free, which is what you want when work queues up.
**LM Studio LM Link** does remote access: your laptop loads and uses a model running on the desktop, at
`localhost:1234`, which is what you want when one machine has the VRAM and the other has your keyboard.
Both are free today and both take an evening. Do not build anything. Do not use GPUStack for this — it
dropped macOS workers.

**One machine, and you want to know what fits.** llmfit. It has an MCP server, so your coding agent
can ask it directly. Stop reading calculator sites.

**You want to rent a GPU occasionally without surprises.** SkyPilot, and use `--dryrun` to see the
per-candidate cost before launch, plus `resources.max_hourly_cost` as a ceiling. If an agent is
issuing the launch, add a `PreToolUse` hook on the launch command — the auto-mode classifier does not
consider dollars.

**You want a knowledge graph that predicts placement across everyone's hardware.** Don't. The
combination space is roughly a million meaningful cells that decay in days as runtimes ship, and the
best-instrumented public effort in this niche collects a few hundred observations a month. The
arithmetic does not close.

---

## The build log

[`build-log/`](build-log/) documents an actual build on actual heterogeneous hardware — Apple silicon,
a consumer CUDA box, a NAS, and occasional rented GPUs — one entry per phase, with pasted output,
what broke, what it cost, and elapsed time. Failure is a first-class field, because that is the part
vendor documentation structurally cannot publish.

Entries appear as phases are completed. Empty sections are honest, not aspirational.

---

## Contributing

Corrections are the most valuable contribution. Open an issue with the claim, a primary source, and
your check date. See the end of [CORRECTIONS.md](CORRECTIONS.md).

Feature requests to turn this into a tool will be declined, with thanks. See "what this is not."
