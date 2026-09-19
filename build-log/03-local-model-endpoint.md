# Phase 03 — Local model endpoint

**Status:** done. Not exposed on the LAN, by decision
**Date:** 2026-09-08
**Elapsed:** ~1 h wall clock, most of it downloading 37 GB of images and models
**Cost:** $0

## Goal

An always-on, OpenAI-compatible model endpoint on the CUDA node from [phase 02](02-linux-box-driver-containers.md), models on the bulk disk, GPU doing the work. Done when a chat completion comes back with the GPU visibly holding the model, it survives a reboot with nobody logged in, and every model has a *measured* tok/s next to its name — the map's rule, not a calculator's number.

## Hardware touched

The phase 02 box: RTX 4070 12 GB, 64 GB DDR4-3200, models on the 1 TB SATA disk. Nothing else.

## What I ran

Ollama, in Docker, pinned. The map's own row for it: local runner, OpenAI-compatible and Anthropic `/v1/messages` endpoints, MIT. llama.cpp + llama-swap is the more controllable stack and a later entry; this gets a working endpoint in an evening on top of exactly what phase 02 built. v0.33.3 was current on 2026-09-08 (released 2026-09-02); `0.34.0-rc1` existed and was not taken.

```yaml
services:
  ollama:
    image: ollama/ollama:0.33.3
    restart: unless-stopped
    ports:
      - "127.0.0.1:11434:11434"     # loopback only
    volumes:
      - /srv/ai-lab/models/ollama:/root/.ollama
    environment:
      OLLAMA_KEEP_ALIVE: 30m
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
```

Loopback only because Ollama has no authentication and the decision on LAN exposure belongs with the SSH decision, which is still deferred. That drops "reachable from the laptop" from the acceptance list and makes the firewall irrelevant to this service.

Models, sized off ollama.com the same day against the 12 GB card. Rule of thumb used: model file ≤ ~9 GB so there's 2–4 GB left for context. That excludes the headline models — `qwen3.6`/`qwen3.8` 27b at 18 GB, `gpt-oss:20b` at 14 GB, `qwen3-coder:30b` at 18 GB — which is the map's point about 12 GB. Or so I thought; see A3.7.

| Model | File | Why |
|---|---|---|
| `qwen3.5:0.8b` | 1.0 GB | proves the pipeline in seconds |
| `qwen3.5:9b` | 6.6 GB | fast, code-leaning, most context headroom |
| `gemma4:12b` | 7.6 GB | largest dense class that fits; general chat |
| `qwen3-coder:30b` | 18 GB | MoE, ~3B active — the experiment |

Both `gemma4` and `qwen3.5` are newer than the assistant that helped pick them knew about. They were chosen by family and size class. The measurements below are the judgement.

## Output

```
$ curl -s http://127.0.0.1:11434/api/version
{"version":"0.33.3"}

$ ss -tln | grep 11434
LISTEN 0      4096       127.0.0.1:11434      0.0.0.0:*

$ docker exec ollama nvidia-smi -L
GPU 0: NVIDIA GeForce RTX 4070 (UUID: GPU-<uuid>)

$ curl -s http://127.0.0.1:11434/api/chat -d '{"model":"qwen3.5:0.8b","messages":[{"role":"user","content":"In one sentence, what is a GPU?"}],"think":false,"stream":false}'
reply: A GPU is a graphics processing unit that runs vectorized mathematical operations much faster than a CPU.
eval: 20 tok in 0.07s = 283.2 tok/s

$ nvidia-smi --query-compute-apps=process_name,used_memory --format=csv,noheader     (sampled mid-request)
/usr/lib/ollama/llama-server, 918 MiB

$ docker exec ollama ollama ps
NAME            SIZE      PROCESSOR    CONTEXT
qwen3.5:0.8b    1.1 GB    100% GPU     4096
```

Measured speed. Same ~40-token prompt for all, thinking off, 256 tokens generated, second (warm) request measured, cold load separate. Numbers are Ollama's own `eval_count`/`eval_duration`.

```
model            file    cold_load_s  prompt_tok/s  gen_tok/s  vram_MiB  split
qwen3.5:0.8b     1.0 GB  2.3          2529          277.5      1446      100% GPU
qwen3.5:9b       6.6 GB  3.0          969           75.9       6442      100% GPU
gemma4:12b       7.6 GB  3.5          882           54.7       8230      100% GPU
qwen3-coder:30b  18 GB   15.7         2043          53.6       10278     45% CPU / 55% GPU
```

Sanity check against the map's bandwidth rule for gemma4: 504 GB/s ÷ 7.6 GB ≈ 66 tok/s ceiling; measured 54.7. Bandwidth-bound.

**The MoE row is the finding.** `qwen3-coder:30b` does not fit the card. Ollama put 45% of it in system RAM and it generated at 53.6 tok/s — the same speed as `gemma4:12b` sitting entirely in VRAM, from a model 2.4× the size. ~3B of 30B parameters are active per token, so the bytes moved per token stay small even when half come from DDR4. `free -g` during the run: 5 GB used, 57 GB page cache. The price is cold load, 15.7 s off the SATA disk against ~3 s for the dense models.

So the working rule for a 12 GB card with a lot of RAM behind it: dense models up to ~8 GB in VRAM, *or* MoE models up to what RAM holds, at about the same generation speed. The map's "12 GB is the real ceiling" is a dense-model ceiling. The build-log README now says so.

After a reboot, nobody logged in:

```
$ docker inspect ollama --format '{{.HostConfig.RestartPolicy.Name}}  {{.State.StartedAt}}'
unless-stopped  2026-09-08T22:03:46Z                # ~1 min after boot

$ curl -s http://127.0.0.1:11434/v1/models          # all four listed
$ (qwen3.5:9b, first request after reboot)          # 8 tok at 73.8 tok/s, 100% GPU
$ findmnt /srv/ai-lab; systemctl is-active containerd docker
/dev/sda1 /srv/ai-lab   active active
```

Disk: models 32 GB on the bulk disk, root unchanged.

## What broke

**1. Thinking models spend `max_tokens` before they answer.** First OpenAI-style request, `max_tokens: 80`:

```
content: ""
reasoning: "Thinking Process:\n\n1.  **Analyze the Request:** ..."
finish_reason: length    completion_tokens: 80
```

`qwen3.5` reasons first, Ollama returns that in a separate `reasoning` field, and it counts against the budget. Empty answer, no error. `"think": false` on the native API, or a generous `max_tokens`, fixes it. `gemma4` doesn't do this. Anyone pointing a client at this endpoint hits it on the first short request.

**2. The first speed run was wrong and looked fine.** Prompt tok/s of 5 and 3 for the two big models — the cold load folded into the prompt timing. One VRAM figure from the wrong process, because `ollama stop a b c` only unloads `a`. Re-run: unload everything, one warm-up request, measure the second, one model at a time. Only the re-run is in the table. A number with a method attached is a measurement; the first table was a printout.

**3. The bulk disk had 60 GB on it that the lab didn't put there.** `df` said 114G used; images and models came to ~53G. A container with the disk mounted read-only found a 63 GB Steam library. The operator had installed it there the same afternoon, contrary to what the private record said at the time. Record corrected to match the disk. Not a fault — it's their disk — but "the record and the disk disagree" is exactly the thing these logs exist to catch, and `df` caught it in an hour.

## What I would do differently

Test the MoE first, not last. It was a curiosity bolted onto the end and it turned out to be the most useful number of the day.

Pick the measurement method before pulling models. The re-run cost five minutes; publishing the first table would have cost more.

Warm the disk cache before timing a cold load, or say which one you measured. gemma4's first-ever load was 22 s; its "cold" load after the file had been read once was 3.5 s. Both are true; only one is what a user sees after a reboot.

## Deferred, by decision

- **LAN exposure.** Bound to loopback. When SSH is revisited, this is revisited with it, and the acceptance check "reachable from the laptop" comes back.
- **llama.cpp + llama-swap.** The controllable stack. Worth its own entry, particularly to see whether explicit expert placement beats Ollama's 45/55 split.

## Acceptance check

| | Check | Result |
|---|---|---|
| A3.1 | endpoint answers, models listed | pass |
| A3.2 | inference on the GPU — process holding VRAM mid-request | pass |
| A3.3 | reachable from the laptop | dropped — not exposed |
| A3.4 | container, models and GPU back after a reboot, unattended | pass |
| A3.5 | models on the bulk disk, root unchanged | pass |
| A3.6 | measured tok/s per model, method stated | pass |
| A3.7 | MoE spill experiment | measured — 53.6 tok/s at 45/55 |

Phase closed. The local endpoint exists and is fast enough to use. It is reachable from one chair.
