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

**What this line failed to do is say what the moved split cost.** It recorded that the MoE lost VRAM at 64k and stopped there. The answer, measured in [07](07-maintenance-pass.md), is 53.6 → 38.2 tok/s, which inverts the phase 03 headline: at 64k the 30B MoE is slower than the 12B dense model, not equal to it. The number was one command away and the entry noted the cause without checking the effect.

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
    local model="${CLAUDE_LOCAL_MODEL:-laguna-xs-2.1}"   # see the bake-off below
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

## Bake-off, 2026-09-19: four local agentic coders, one exam

One model failing twice doesn't prove local models can't do this. Since the first trial, three newer models marketed specifically for agentic coding have appeared. They're all the same size class as qwen3-coder: a 30B mixture-of-experts with ~3B active, so they run on this machine the same way, by spilling into RAM. I put all four through the rematch exam, with qwen3-coder rerun under identical clean conditions. In its rematch, a leftover file of its own had been sitting in the home directory, which wasn't a fair start.

The harness, [`scripts/agent-bakeoff.py`](scripts/agent-bakeoff.py), refuses to start if a previous contestant's files are still around. It unloads every model and warms only the contestant, so load time isn't scored. Every model gets the same task, tools, turn limit and permission mode, one at a time. **It grades by running each tool against the live endpoint** and looking for the real values (`Q4_K_M`, `30.5B`). That's exactly where qwen3-coder failed twice while its own tests passed.

Before trusting it, **I tested the grader on two answers whose correctness was already known.** The Opus control from the first trial passed every check. The qwen rematch failed on correctness while its tests showed "5 passed". Then, because the grader failed all four contestants, I read every contestant's actual output by hand. It was right each time, but the four failed for different reasons:

```
                          qwen3-coder:30b   laguna-xs-2.1   north-mini-code-1.0   nemotron-3.5-lightning
size / share on GPU       18 GB / 43%       20 GB / 39%     18 GB / 47%           25 GB / 35%
tool works vs live API    no - crashes      no - 'unknown'  no - all 5 crash      no - columns blank
looked at the API (curl)  0                 0               0                     0
used required filename    yes               yes             no  (11 files)        no  (ollama_query.py)
stayed in project folder  NO - 4 files ~    yes             yes                   yes
finished in < 40 turns    yes (17)          no              no                    no
tool calls / rejected     16 / 6            117 / 23        80 / 9                60 / 25
wall time                 421 s             891 s           1,486 s               1,097 s
```

**None of the four produced a working tool, and none of the four checked the API: 0 of 273 actions.** Each made the same assumption about where Ollama puts parameter size and quantization (top level, rather than under `details`), got it wrong, and never ran the one `curl` that would have shown it. Opus got it right in 52 seconds. The marketing copy describes all three newer models as built for agentic engineering. On this exam, "agentic" meant using lots of tools, not using the one that mattered.

Two things came out better. The newer models **kept to their project folders**; qwen3-coder has now scattered files into the home directory on all three of its runs. And laguna came closest: its tool runs, its tests pass, and only those two fields are wrong.

**No local model tested here is a trustworthy coding agent.** `claude-local` now defaults to laguna, because it stays in its folder, and it still asks before every write.

## Fifth contestant: an 80B, to test whether the ceiling is model size

The four above are all ~30B. If the failure is capacity, a much larger model should clear the bar. `Qwen3-Next-80B-A3B` at Q4_K_S — 80B total, 3B active, 45.5 GB, running at 40 tok/s on this box (see [03](03-local-model-endpoint.md)) — took the identical exam: same task, same allowed tools, same 45-minute limit, same grader.

```
                          qwen3-next-80b    (best of the four 30B)
wall time                    166 s            421 s
turns / tool calls           4 / 3            17 / 16
curl calls                   0                0
produced a tool              yes              yes (laguna, qwen3-coder)
table with real values       YES  <- first    no
--json valid                 YES  <- first    no
error path exits non-zero    YES              yes
its own tests pass           no (3 failed)    yes (laguna, on wrong data)
followed the spec            no               partly
```

**It is by far the best result, and it still fails.** Six times faster than the best 30B, and the first local model whose tool renders a real table with real quantizations (`Q4_K_S`, `Q8_0`) and real parameter sizes (`79.7B`, `873.44M`), emits valid `--json`, and exits non-zero on an unreachable server. Everything the four before it got wrong, it got right.

Then the one requirement the whole task is built around:

```python
def fetch_ollama_ps():
    with urllib.request.urlopen("http://127.0.0.1:11434/api/ps") as response:
        data = json.loads(response.read())
        return data.get("processes", [])      # Ollama returns {"models": [...]}
```

`/api/ps` has no `processes` key. The `.get(…, [])` default turns a wrong guess into an empty list, so **every model reports LOADED "no", permanently** — verified with a model provably resident:

```
$ curl -s /api/ps -> resident: ['qwen3.5:0.8b']
$ python3 ollama_info.py | grep 0.8b
  qwen3.5:0.8b    1.0    873.44M    Q8_0    no
  {"name": "qwen3.5:0.8b", …, "loaded": false, "size_vram_gb": null}
```

**A fifth model, four times the parameters, invented a field name and never ran the one command that would have corrected it.** Five of five contestants, 276 tool actions, **zero curls**. Its own three tests would have caught nothing either — they fail to run at all (`Mock` misuse, and `urllib` referenced but never imported), so it validated nothing and reported success anyway.

It also ignored three explicit instructions — both required filenames (`ollama_models.py`, `test_ollama_models.py`) and the specified runner (`uvx pytest -q`, the one form that was permitted). It ran `python3 -m pytest`, was denied, and **stopped after a single denial** to ask the human, where the four smaller models pushed through 6–25 denials.

**So the ceiling is not model size.** A 2.7× larger, far more capable model writes much better code and then fails the same way, for the same reason: it does not check its assumptions against a reachable source of truth, and its tests encode the assumption rather than testing it. That is the identical failure this log keeps recording in its *own* checks — a proxy passing while the outcome is false. The difference is that a person eventually notices; the model reported "the tests are designed to mock the HTTP layer" and considered it verified.

`claude-local` stays in ask-mode.

## Asking for the assumptions changes what you get

2026-09-20, same 80B, this time in a chat window rather than an agent harness,
and with one sentence added to the task: *"before writing any code, list every
assumption you are making about the JSON, and mark each one VERIFIED or
GUESSED."* No tools, no network, so nothing could be checked.

**It listed them.** Roughly fifteen assumptions, and crucially it marked the two
that matter — `running` and `vram` on `/api/ps` — as **GUESSED**. The same model
that silently invented field names in the exam above flagged them when asked.

The code was still wrong. Run against the live endpoint:

```
Name                            Size(GB)   Params     Quant  Loaded  VRAM(GB)
qwen3-next-80b:q4ks                 42.4      80B      q4ks      no       0.0
qwen3.5:0.8b                         1.0       8B      0.8b      no       0.0
```

**The model that wrote the script was resident at that moment with 10.5 GB in
VRAM, and its own tool reports `Loaded: no, VRAM 0.0`.** It cannot see itself.
`/api/ps` has no `running` field — presence *is* running — and the VRAM field is
`size_vram`, not `vram`. Two of six columns survive.

Three things in the assumption list are worth more than the code:

**It marked four assumptions VERIFIED with no network access.** The sharpest:

> `name: matching /api/tags model names — VERIFIED (must match for correlation)`

Circular: verified because the script requires it. A design requirement restated
as a confirmed fact. The rest lean on "standard API design" and "well-known
convention" — recall, presented as verification.

**It hypothesised the correct structure and then talked itself out of it.** The
tags section contains `details: object — GUESSED (Ollama API may nest model
metadata)`. Eleven lines later: `Parameter size: Not directly exposed by Ollama
API — GUESSED`. That is false, and it had already guessed the answer:
`details.parameter_size` and `details.quantization_level` are exactly where the
two fabricated columns live. Having suspected the nested object, it asserted the
data did not exist and regexed filenames instead — which is why the Quant column
prints `latest` and `30b`, and why a 873M model is labelled "8B".

**It closed with "this script is production-ready under the assumptions
stated"** — after fifteen guesses, four mislabelled, two fatal.

**The finding is the behavioural one.** Same model, same task, one added
sentence: silent invention becomes labelled invention. It still does not act on
its own uncertainty — it never says "I should check this first" — but it
surfaces it, which is the difference between a bug caught in review and one
caught in production. That is cheap enough to make a standing rule, and it is
now in the `claude-local` header:

> Ask for assumptions before code, marked VERIFIED or GUESSED. Then check every
> GUESSED one yourself, and treat every VERIFIED one as GUESSED too, because the
> model cannot tell the difference.

### And then it does nothing in the agent loop

The obvious next question: the rule works in chat, but does it make the model
*act* — does it run the `curl` it has been given? Same exam, same harness, same
45-minute limit, with the rule appended to the task text (not the system prompt,
for the reason below) and this line added:

> *"You have curl. Anything still GUESSED when you finish is a choice you made."*

```
wall 175 s | turns 4 | tool calls 3 | curl calls 0 | rejected 1
```

**Zero curls.** Seven contestants now, **279 tool actions, not one.**

There was no ASSUMPTIONS block either — not in a file, not in a message. The rule
that reliably produces one in chat produced nothing here. What it did instead was
identical to the unprompted run: write `ollama_info.py`, write
`test_ollama_info.py`, run `python3 -m pytest`, get denied, stop and ask for
approval.

In agent mode it ignored **four** explicit instructions from the same task text:
both required filenames, the specified runner (`uvx pytest -q`, the only
permitted form), and "using only the standard library" — it imported `requests`.
And it reverted to the invention from the original exam:

```python
return data.get("processes", [])      # /api/ps top-level keys: ['models']
"quantization": model["details"].get("quantization", "unknown")   # real: quantization_level
```

Run against the live endpoint, the tool is once again blind to the model that
wrote it — resident with 10.8 GB in VRAM, reported as `LOADED no`.

**Two ways the fix fails to reach the agent, both measured rather than assumed.**
First, as a Modelfile `SYSTEM` it is silently overridden: the same question asked
with and without a client system message produces the ASSUMPTIONS block only
without, and with one the answer regressed to an invented top-level
`quantization` field plus a non-stdlib import. Claude Code always sends a system
prompt, so the `-checked` variant is inert under `claude-local`. Second, moved
into the task text where nothing can override it, it is simply ignored — along
with three other instructions sitting beside it.

**The conclusion is narrow and worth stating plainly: prompt-level fixes do not
survive into the agent loop.** The chat result is real and reproducible, and it
is a *review* aid — it makes a human reading the output better informed. It is
not an agent fix. An agent that ignores four explicit instructions in its own
task will ignore a fifth about checking its assumptions.
 The 80B is now the best available *drafting* model on this machine — its code is closest to correct and it is folder-disciplined — but "best" still means every line needs reading.

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
