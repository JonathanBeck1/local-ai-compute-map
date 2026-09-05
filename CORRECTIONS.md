# Corrections

Claims about personal AI compute that are widely repeated and are false, stale, or misquoted as of
the check date. This page exists first because it is the reason to trust the rest of the repo: the
same method that produced the map produced these, and several of them were errors in my own earlier
notes before they were anyone else's.

Each entry gives the claim as usually stated, what is actually true, the primary source, and the date
I checked it.

---

## 1. "GPUStack gives you one cluster across NVIDIA, AMD, and Apple silicon"

**Status: false since v2.** — verified 2026-09-05

GPUStack is still routinely recommended as the single free tool that spans a Mac and a CUDA box. Its
own README now states that macOS is not supported for GPUStack worker nodes. The maintainer's
explanation, in the project's discussions, is that from v2 all models run inside containers and macOS
does not permit GPU access from containers. The v2 line landed 2025-11-23.

This matters because GPUStack is the tool most often cited as proof that the heterogeneous
Apple + NVIDIA fleet problem is already solved by free software. For inference across a Mac and a PC
today, the working answers are exo and NVIDIA PAIR, not GPUStack.

- https://github.com/gpustack/gpustack
- https://github.com/gpustack/gpustack/discussions/3704

## 2. "Perplexity said macOS is not on the roadmap for local AI"

**Status: misquote, and superseded.** — verified 2026-09-05

The widely-circulated line traces to VentureBeat's own editorial phrasing that macOS was
"conspicuously absent from the roadmap." Perplexity's actual quoted statement was "We're very focused
right now on Nvidia hardware," which is a statement of present focus, not a roadmap exclusion.

It is also superseded twice over. Perplexity shipped a Mac product on 2026-04-16, and on 2026-09-01
shipped Hybrid Compute for Apple silicon: a task starts in the cloud, steps touching private data are
routed to a local model, and an on-device classifier substitutes stand-ins before anything leaves the
machine. It requires 24 GB of unified memory.

- https://venturebeat.com/infrastructure/perplexity-partners-with-nvidia-to-launch-portable-computer-a-fully-local-ai-agent-with-zero-token-costs
- https://www.macstories.net/news/perplexity-introduces-hybrid-compute-to-keep-sensitive-data-local/

## 3. "NVIDIA will never route work to Apple silicon"

**Status: false as of 2026-09-03.** — verified 2026-09-05

This was a reasonable inference from NVIDIA's product line right up until it wasn't. Brev Connect is
Linux-only. Sync Cluster Assistant handles DGX Sparks only. NeMo Switchyard routes across models, not
machines. The conclusion that NVIDIA structurally would not touch macOS was widely drawn, including
by me.

On 2026-09-03 NVIDIA published PAIR (Personal AI Router), Apache-2.0, which discovers machines on a
local network and routes inference requests across GeForce RTX 20-series and newer, RTX PRO, DGX
Spark, **and Apple M4 or newer silicon**, on Windows 11, Linux, and macOS, integrating with Ollama
and LM Studio.

See the map for what PAIR does not do, which is substantial. But the categorical claim is dead.

- https://developer.nvidia.com/blog/nvidia-pair-virtual-inference-router-expands-available-compute-on-your-local-network/
- https://github.com/NVIDIA/Personal-AI-Router

## 4. "exo raised about $250K from crypto funds"

**Status: wrong company.** — verified 2026-09-05

The Tracxn page commonly cited for this describes a different Exo Labs: a Seattle microscope-camera
company founded in 2011, since deadpooled, which raised roughly $2.98M in 2012–2014. The exo that
builds heterogeneous local AI clustering is a London company founded in March 2024 by Alex Cheema and
Mohamed Baioumy. Its funding is not public; contemporaneous coverage says only that it raised an
undisclosed amount from private investors.

If you are sizing this category by how much money it has attracted, do not count the $250K.

- https://github.com/exo-explore/exo
- https://www.canonical.cc/portfolio/exo-labs

## 5. "LM Studio is bootstrapped"

**Status: false.** — verified 2026-09-05

LM Studio raised $19.32M, in a round dated 2025-05-30. It is frequently described as a bootstrapped
indie project in comparisons against funded competitors.

- https://www.cbinsights.com/company/lm-studio/financials

## 6. "A VRAM calculator tells you how fast a model will run"

**Status: category error.** — verified 2026-09-05

Fit and speed are different questions. Whether weights fit is arithmetic on parameter count,
quantization, and context. Decode speed on a memory-bound local setup is approximately memory
bandwidth divided by active bytes per token, which is why an RTX 4070 at 504 GB/s decodes a
12 GB-resident model faster than a DGX Spark at 273 GB/s despite the Spark having 128 GB of unified
memory. Most published calculators answer the fit question and are silent, or wrong, on the speed
question.

Two of the tools that do attempt cost or time estimates say so themselves: Train-in-Silence's README
states its estimation model is fixed with no built-in calibration, and quantprobe labels its Mac
presets as extrapolated rather than measured.

- https://github.com/hlpun/Train-in-Silence
- https://github.com/AlexsJones/llmfit

---

## How to report a correction

Open an issue with the claim, the primary source that contradicts it, and the date you checked. A
correction without a primary source and a date will be treated as a rumour, which is the whole
problem this page exists to address. Corrections to my errors are especially welcome and will be
listed here with attribution.
