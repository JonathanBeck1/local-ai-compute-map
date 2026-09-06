# Corrections

Claims about local AI compute that get repeated and are wrong. Four of these were wrong in my own notes first, which is the reason this page leads the repo instead of hiding at the bottom.

Each one: the claim as usually stated, what's actually true, the source, the date I checked.

## 1. GPUStack gives you one cluster across NVIDIA, AMD and Apple silicon

Wrong since v2. Checked 2026-09-05.

Its README says "macOS is not supported for GPUStack worker nodes." The maintainer's explanation in the project discussions: from v2 all models run in containers, and macOS won't give a container GPU access. The v2 line landed 2025-11-23.

This one matters because GPUStack is the tool most often cited as proof that free software already solves the mixed Mac and NVIDIA problem. It doesn't, and hasn't for nine months. For inference across a Mac and a PC today the working answers are exo and PAIR.

- https://github.com/gpustack/gpustack
- https://github.com/gpustack/gpustack/discussions/3704

## 2. Perplexity said macOS is not on the roadmap

Misquote, and overtaken anyway. Checked 2026-09-05.

The line traces to VentureBeat's own phrasing, that macOS was "conspicuously absent from the roadmap." What Perplexity actually said was "We're very focused right now on Nvidia hardware." That's present focus, not exclusion.

They shipped a Mac product on 2026-04-16, and on 2026-09-01 shipped Hybrid Compute for Apple silicon: a task starts in the cloud, steps touching private data run locally, an on-device classifier swaps in stand-ins before anything leaves. Needs 24 GB unified.

- https://venturebeat.com/infrastructure/perplexity-partners-with-nvidia-to-launch-portable-computer-a-fully-local-ai-agent-with-zero-token-costs
- https://www.macstories.net/news/perplexity-introduces-hybrid-compute-to-keep-sensitive-data-local/

## 3. NVIDIA will never route work to Apple silicon

Wrong as of 2026-09-03. Checked 2026-09-05.

A fair read of their product line until it wasn't. Brev Connect is Linux only, Sync handles DGX Sparks only, Switchyard routes models rather than machines. I drew the conclusion too, in writing.

Then on 2026-09-03 NVIDIA published PAIR, Apache-2.0, which discovers machines on a LAN and routes inference across GeForce RTX 20-series and newer, RTX PRO, DGX Spark, and Apple M4 or newer, on Windows 11, Linux and macOS, through Ollama and LM Studio.

What PAIR doesn't do is in the [map](README.md), and it's a long list. But the categorical version of this claim is dead.

- https://developer.nvidia.com/blog/nvidia-pair-virtual-inference-router-expands-available-compute-on-your-local-network/
- https://github.com/NVIDIA/Personal-AI-Router

## 4. LM Link routes work across your machines, free, up to 5 devices

Wrong three ways, and this was mine. Checked 2026-09-05.

It is remote access, not routing. Its docs say you "load models on remote devices and use them as if they were local" — no distribution of work, no balancing. There is no stated device limit anywhere, so the "5 devices" figure was invented. And it's free during the preview period only: LM Studio says there will be "both free as well as paid plans once the feature is released for General Availability."

Worth separating from PAIR, which does route requests. They solve different problems and get treated as interchangeable constantly, including by me until I opened the page.

- https://lmstudio.ai/link

## 5. exo raised about $250K from crypto funds

Wrong company. Checked 2026-09-05.

The Tracxn page usually cited is a different Exo Labs: a Seattle microscope-camera business founded 2011, since dead, which raised about $2.98M in 2012–2014. The exo that does heterogeneous local clustering is London, founded March 2024 by Alex Cheema and Mohamed Baioumy, and its funding isn't public. Coverage at the time says only an undisclosed amount from private investors.

If you're sizing this category by money raised, don't count the $250K.

- https://github.com/exo-explore/exo
- https://www.canonical.cc/portfolio/exo-labs

## 6. LM Studio is bootstrapped

$19.32M, round dated 2025-05-30. Checked 2026-09-05.

- https://www.cbinsights.com/company/lm-studio/financials

## 7. A VRAM calculator tells you how fast a model will run

Category error. Checked 2026-09-05.

Fit and speed are different questions. Fit is arithmetic on parameters, quantization and context. Decode speed on a memory-bound machine is roughly bandwidth over active bytes per token, which is why an RTX 4070 at 504 GB/s beats a DGX Spark at 273 GB/s on anything that fits in 12 GB, despite the Spark having ten times the memory. Most calculators answer the first question and say nothing useful about the second.

Two tools that do attempt time or cost say so themselves: Train-in-Silence's README calls its estimation model "fixed with no built-in calibration," and quantprobe labels its Mac presets extrapolated rather than measured.

- https://github.com/hlpun/Train-in-Silence
- https://github.com/AlexsJones/llmfit

## Reporting one

Open an issue with the claim, the primary source, and your check date. No source and no date means I can't act on it, which is the problem this page exists for. Corrections to my own errors are the most useful kind and get listed here with credit.
