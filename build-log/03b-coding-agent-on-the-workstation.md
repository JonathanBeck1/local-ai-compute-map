# Phase 03b — Coding agent on the workstation

**Status:** done
**Date:** 2026-09-11
**Elapsed:** ~1 h, of which ~10 min was the local agent run
**Cost:** $0.32 — the control run on the paid model

## Goal

The workload on this box is coding-agent tasks. Two questions, both answerable with numbers: does the map's fit tool (llmfit) tell the truth about this hardware, and is a local 30B coder good enough to run Claude Code on, zero-cost, instead of the paid model?

## Hardware touched

The [phase 02](02-linux-box-driver-containers.md) desktop, with the [phase 03](03-local-model-endpoint.md) Ollama endpoint. One change: Ollama's context raised from its 4,096 default to 65,536, because Claude Code's system prompt doesn't fit in 4k and Ollama's own Claude Code doc says 64k+.

## What I ran

**llmfit 1.1.15** (released 2026-09-10), installed with `uv tool install -U llmfit`, no root.

```sh
llmfit doctor                          # what it thinks the hardware is
llmfit recommend --json --use-case coding --limit 5
llmfit bench --all                     # measures the installed Ollama models itself, 3 runs each
claude mcp add --scope user llmfit -- ~/.local/bin/llmfit serve --mcp
```

**Claude Code on a local model**, per [docs.ollama.com/integrations/claude-code](https://docs.ollama.com/integrations/claude-code):

```sh
ANTHROPIC_BASE_URL=http://127.0.0.1:11434 ANTHROPIC_AUTH_TOKEN=ollama ANTHROPIC_API_KEY="" \
  claude -p "$(cat TASK.md)" --model qwen3-coder:30b --output-format json \
  --allowedTools "Read,Write,Edit,Glob,Grep,Bash(uvx pytest:*),Bash(ls:*),Bash(cat:*)" --max-turns 40
```

The same command with `--model claude-opus-5` and no env override, in a second empty directory, as the control.

The task, in full:

> In this empty directory, create `ollama_models.py`: a Python 3 script using only the standard library that queries a local Ollama server at http://127.0.0.1:11434 via GET /api/tags and GET /api/ps, and prints a table of installed models with columns: name, size in GB (one decimal), parameter size, quantization, and LOADED (yes/no; if yes, also show the size_vram in GB). Support a `--json` flag that prints the merged data as JSON instead of a table. Exit non-zero with a clear message if the server is unreachable.
>
> Then create `test_ollama_models.py` with pytest tests that mock the HTTP layer (no network access during tests) and cover: (1) table rendering with one loaded and one unloaded model, (2) the --json output shape, (3) the unreachable-server error path.
>
> Run the tests with `uvx pytest -q` and fix things until they pass. When done, print the final test output.

Small on purpose: finishable, and checkable without opinion. Neither run was allowed to `curl` the live API.

**Verification, the same for both:** I re-ran the tests myself, ran the script against the real endpoint, forced the unreachable path, read the code. The agent's own claim of success counted for nothing.

## Output

llmfit sees the machine correctly — Ryzen 9, 62.7 GB, RTX 4070 12.0 GB, CUDA. Its bench against the live endpoint, next to the phase 03 measurements:

```
model            llmfit bench   phase 03    TTFT
qwen3.5:0.8b     272.3          277.5       12 ms
qwen3.5:9b        75.0           75.9       53 ms
gemma4:12b        54.4           54.7       60 ms
qwen3-coder:30b   56.3           53.6      121 ms
```

Two methods, within 2% on every row. Its *estimates* are another matter: ~48 tok/s predicted for a 12B-class dense model, 34–67 for a 9B depending on quant — 15–30% under what the card does. For `--use-case coding` it recommends Qwen2.5-Coder 7B and 14B — the 2024 generation — and never surfaces the 30B MoE, because its fit model treats spilling into RAM as not fitting. On this box its recommendations are a floor.

The agent trial:

```
                          local: qwen3-coder:30b     control: claude-opus-5
wall time                 580 s                      52 s
turns                     22                         6
output tokens             8,801                      4,338
tests, re-run by me       3 passed                   3 passed
runs against live Ollama  yes                        yes
unreachable path          correct, exit 1            correct, exit 1
PARAMS / QUANT columns    empty, every model         correct
unrequested files         README.md, FINAL_TEST_OUTPUT.txt   none
extras                    —                          --host flag, distinct error kinds, sorted rows
cost                      $0                         $0.32
GPU during run            45% avg, 57/43 CPU/GPU     —
```

The local model's finishing message: *"All tests pass successfully (3/3 tests passing). All requirements were met."* True and false at once — see below.

At 64k context the MoE's split moved from 45/55 to 57% CPU / 43% GPU; the KV cache took the VRAM. The two dense models are unaffected at 64k (re-measured 54.8 and 75.6 tok/s, still 100% GPU).

## What broke

**1. Green tests, wrong output.** The local agent's PARAMS and QUANT columns are empty for every model. It read `tag.get('parameters')` and `tag.get('quantization')`; Ollama returns them as `details.parameter_size` and `details.quantization_level`. It never saw a real response, guessed the shape, wrote the mock to match the guess, and the tests passed against the mock. Its tests are evidence the code matches its belief, not the API. Only running the tool against the live endpoint caught it — which is why that step is in the verification and not optional. The control got `details.*` right without looking either; it knew the API. Also, the local "GB" is GiB.

**2. llmfit's MCP server isn't in its docs.** The map's row says it ships one. The README and every file under `docs/` say nothing. It exists — `llmfit serve --mcp`, six tools, found by listing the source tree — so the map is right and the docs have a gap. Reported upstream would be the right move.

**3. Claude Code prices a free model.** `total_cost_usd: 1.097` in the local run's JSON. It's the estimate for an unrecognised model name at some default rate. Actual cost, zero. Anyone summing costs out of these result files would be wrong.

**4. Found eight days later: the local agent wrote outside its directory.** An [inventory of the workstation](00b-desktop-backup.md) turned up stray files in the home directory, timestamped inside the local run's window (14:03 to 14:12) and before the control run. There were two: `test_ollama_models.py` and `ollama_models.py`, written at 14:04 and 14:05. The inventory first reported only one, for reasons covered in 00b. Neither matches the run's final files, so they're early drafts that qwen3-coder wrote to the wrong path before writing the real ones in the folder it had been given. The run was allowed `Write` with no path restriction, and it used that outside its directory. It was harmless here. It's also exactly what makes an unattended local agent risky, and the verification above missed it because it only looked inside the working directory. **Check where an agent wrote, not only what it wrote where you expected.**

## Rematch, 2026-09-19: allowed to check, it didn't

The obvious objection to the result above is that the local model had no way to check the API, so its guess was unavoidable. The fix was one permission: let it `curl` the real endpoint. I added `Bash(curl:*)` to its allowed tools, and changed nothing else: same task, same model, a fresh folder. I **didn't tell it to look**, because the question was whether it would choose to. Every action was recorded, and a timestamp marker was set so that writes *anywhere* in the home directory could be found afterwards, not just in its folder.

```
                              first run        rematch
allowed to curl the API       no               yes
curl calls made               -                0 of 29 actions
wall time                     580 s            1,344 s
commands rejected             -                9  (python, mv, cd && ... -- not on its list)
files in its project folder   4                0
files written to ~ instead    2                6, plus __pycache__ and .pytest_cache
PARAMS / QUANT columns        empty            empty -- the identical model.get('parameters') guess
its tests, re-run by me       3 passed         3 passed / 3 passed / 1 failed
its own verdict               "successfully"   "successfully"
```

**It never looked.** It made the identical wrong guess, wrote tests that encode the guess, and reported success. Giving it the means to check changed nothing, because it doesn't check. **The limit is behaviour, not access.**

**It wrote everything in the wrong place, and that wasn't my launch.** Having blamed the wrong cause for an outage elsewhere in this log, I checked. The recording's first event shows Claude Code started in exactly the right folder. The model's *first* file path, before it had read anything, was in the home directory. The Opus control kept all its files in its own folder.

**It overwrote a file it hadn't created.** One of the stray drafts from the first run was still sitting in the home directory. Claude Code's read-before-write guard blocked the first two attempts to write it, then allowed the third, because the model had read the file in between. **That guard asks "did you read it?", not "is it yours?"** It doesn't stop an agent that reads first.

### Making it a one-command tool anyway

The mechanics work fine. `claude-local` is a small shell function that points Claude Code at the local endpoint for that one command, so plain `claude` is unaffected:

```bash
claude-local() {
    local url="${CLAUDE_LOCAL_URL:-http://127.0.0.1:11434}"
    local model="${CLAUDE_LOCAL_MODEL:-qwen3-coder:30b}"
    if ! curl -fsS -m 3 "$url/api/version" >/dev/null 2>&1; then
        echo "claude-local: no Ollama endpoint answering at $url" >&2; return 1
    fi
    local mode=()
    case " $* " in
        *" --permission-mode "*) ;;
        *) mode=(--permission-mode "${CLAUDE_LOCAL_MODE:-manual}") ;;
    esac
    ANTHROPIC_BASE_URL="$url" ANTHROPIC_AUTH_TOKEN=ollama ANTHROPIC_API_KEY="" \
        command claude --model "$model" "${mode[@]}" "$@"
}
```

Startup is better than the first number suggested. Claude Code sends the model about 18,000 tokens of instructions. The first run after the model had unloaded took **116 s**, the next **15.6 s**, and the next **0.3 s**. Ollama served 18,016 of those 18,017 tokens from its prompt cache and even reported it in the same `cache_read_input_tokens` field the paid API uses. The model stays warm for 30 minutes.

Because of the rematch, `claude-local` **always starts in the mode that asks before every file write and command**, unless you deliberately choose otherwise. A path in the home directory then shows up as a question, not something already done. It's usable for drafts you approve step by step. It isn't usable headless with writes pre-approved, or in accept-edits or auto mode.

## What I would do differently

Give the agent one read-only probe of the real API, then judge it. Both runs were denied `curl` for fairness; the result is that the trial measured API knowledge as much as coding. A second trial with `Bash(curl http://127.0.0.1:11434/api/*)` allowed would say whether the local model *would have* looked.

Run the control first. Knowing the task takes the paid model 52 seconds and 6 turns frames the local run's 22 turns immediately; I read the local transcript before I had that frame and over-credited it.

## Deferred, by decision

- **`llmfit bench --share`** — contributing this machine's numbers to llmfit's public leaderboard. A 4070 + 64 GB result for a spilled MoE is the kind of row that dataset lacks; it goes out under the operator's GitHub account, so it's their call.
- **NVIDIA PAIR** — waits for the network rebuild, then gets measured against this single-box baseline with the Mac mini as a second node.
- **llama.cpp + llama-swap** — still the open question from phase 03: does explicit expert placement beat Ollama's automatic split.

## Acceptance check

| | Check | Result |
|---|---|---|
| A3b.1 | llmfit detects the hardware correctly | pass |
| A3b.2 | llmfit's measurements agree with an independent method | pass — within 2% on four models |
| A3b.3 | llmfit's MCP server registered and answering in Claude Code | pass — six tools listed via a stdio handshake |
| A3b.4 | Claude Code completes a real task on a local model, verified by hand | **pass with a defect** — tests green, tool runs, two columns wrong |
| A3b.5 | control run on the paid model, same task, same permissions | pass — correct, 52 s |

Phase closed. The working rule for this box: the local coder is a free draft you read; the paid model is what you let finish a task.
