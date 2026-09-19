# Phase 06b — A spend gate, built before there was anything to spend

**Status:** done
**Date:** 2026-09-19
**Elapsed:** ~2.5 h, including one live false positive on the gate's first day
**Cost:** $0 — the point

## Goal

The [map](../README.md) ends one section with: *"Agent-initiated cloud spend is the one thing on this page nothing gates."* Claude Code's permission classifier has a block list — production deploys, IAM grants, force push — and no spend, billing or budget criterion anywhere in it. This phase builds the gate.

The budget is **$0**, because I don't want to spend anything on cloud compute right now. That turns out not to block the work at all. At $0 the policy is simply *no agent may launch paid compute*, and the whole thing can be built and tested without a cloud account, credentials or a single launch.

It also sets the order. **The gate goes in before any account exists that could spend money.** A gate you add after an agent can already launch GPUs is a gate you're racing. The same lesson came up twice elsewhere in this log: put the safety net in before the risky change.

## Hardware touched

None beyond the workstation. No cloud account, no cloud CLI, no credentials. I checked before starting:

```
$ for c in sky runpodctl vastai aws gcloud az dstack modal terraform pulumi; do command -v $c; done
(nothing)
$ ls -d ~/.aws ~/.config/gcloud ~/.azure ~/.runpod ~/.sky
(nothing)
```

## What I ran

A Claude Code `PreToolUse` hook on the Bash tool, at user scope, so it covers every session on the machine, including Claude itself. Scripts: [`scripts/spend-gate.py`](scripts/spend-gate.py) and [`scripts/test_spend_gate.py`](scripts/test_spend_gate.py).

```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "Bash",
      "hooks": [{ "type": "command", "command": "python3 ~/.claude/hooks/spend-gate.py", "timeout": 10 }]
    }]
  }
}
```

The policy is one file, `~/.config/spend-gate/config.json`:

```json
{ "monthly_cap_usd": 0 }
```

At `$0`, anything that would provision paid compute is **denied**. Above `$0` it **asks**, and an `ask` prompts even in auto mode. `--dryrun` is always allowed, since it only prints a price. Every decision goes to an append-only log.

**The design problem is telling execution apart from text.** A naive gate greps for `sky launch` and blocks it. That breaks immediately, because my own commit messages, grep patterns and notes say `sky launch` all the time. Here, `git commit -m "notes on sky launch"` has to pass and `bash -c "sky launch"` must not. So the gate parses: it works out which programs a command would actually execute. It follows `bash -c`, `eval`, `$(…)`, backticks, `sudo`/`env`/`timeout`/`nohup` wrappers, `docker run … sh -c`, heredocs fed to a shell or to Python, and scripts it's pointed at, one level deep. Text that's only quoted is left alone.

It covers SkyPilot, RunPod, vast.ai, AWS, GCP, Azure, dstack, Modal, Terraform/OpenTofu, Pulumi, and the Lambda and RunPod HTTP launch APIs.

The map guessed this would be *"~60 lines around `sky launch --dryrun`."* **It's about 300, plus a test suite.** The 60-line version is the naive grep, and the naive grep blocks your commit messages.

## Output

The test suite, which is self-contained and changes nothing:

```
$ python3 test_spend_gate.py
ok    15/15  direct launches (expect deny)
ok    19/19  wrapped / indirect (expect deny)
ok    12/12  regression: bugs found while building (expect deny)
ok     7/7   regression: found in production (the gate blocked its own PR) (expect allow)
ok     7/7   python read with its parser, not a regex (expect deny)
ok     6/6   must pass: normal work (expect allow)
ok     8/8   must pass: spend words that are only text (expect allow)
ok    13/13  must pass: read-only cloud commands (expect allow)

0 failure(s)
```

The test I trust more is a replay of **every Bash command Claude ran on this machine over this whole build**, fed through the gate. None of them launched cloud compute, so any block would be a false positive that would have broken real work:

```
real commands found: 207
false positives (blocked/asked on a real, harmless command): 0
latency per command: median 17 ms, p95 18 ms, max 51 ms
```

**Then the 208th real command was a false positive** — see What broke 7. After the fix, the replay was re-run over everything including that command, from the directory most likely to trip relative-path checks:

```
real commands: 219  |  deliberate launches still blocked: 2/2  |  false positives: 0
```

Then the acceptance test: with the gate installed, **Claude tried to launch a GPU in the same session.** SkyPilot isn't installed, so this was risk-free either way. The point was to prove the gate intercepts before anything runs:

```
$ sky launch -c gate-acceptance-test --gpus A100:1 task.yaml
PreToolUse:Bash hook error: spend-gate: blocked `sky launch` -- it would launch paid
cloud compute, and the monthly cap is $0 (~/.config/spend-gate/config.json). Only the
user can raise the cap. A `--dryrun` to see the price is allowed.

$ bash -c "cd /tmp && sky launch -c sneaky --gpus H100:8 big.yaml"
PreToolUse:Bash hook error: spend-gate: blocked `sky launch` -- ...

$ cat ~/.local/state/spend-gate/decisions.jsonl
2026-09-19T13:15:47-0400  DENY  cap=$0  'sky launch -c gate-acceptance-test --gpus A100:1 task.yaml'
2026-09-19T13:15:54-0400  DENY  cap=$0  'bash -c "cd /tmp && sky launch -c sneaky --gpus H100:8 big.yaml"'
```

In the same session, ordinary commands (`uname`, `git`, `curl` to the local model endpoint) went through unaffected.

## What broke

Six holes, all found by writing adversarial test cases **before** the gate was installed. Every one would have been a working bypass. Each is now a named regression case in the suite, so none can quietly reopen.

**1. A shebang made whole scripts invisible.** The first version joined a script's lines with `;` before parsing. `#!/bin/bash` then became a comment that ran to the end of the *entire script*. Any script's contents were invisible to the gate, which is exactly how a malicious script would get past.

**2. Comments ate their own newline.** Python's `shlex` consumes the newline when it strips a comment, merging the next line into the current command. That let `sky launch big.yaml # note` followed by a `sky launch --dryrun small.yaml` line **smuggle a real launch through the dry-run exemption**, since the merged command contained `--dryrun`. Fixed with a quote-aware comment stripper that keeps every newline.

**3. `-n` was treated as a dry-run flag.** Plenty of tools use `-n` that way, but Azure uses it for the resource name. `az vm create -n my-gpu-box` got through.

**4. Line continuations split a command.** `sky \` then newline then `launch` became two harmless-looking pieces.

**5. A here-string was read as a heredoc.** `<<<` matched the heredoc pattern, so everything after it was treated as heredoc data and dropped from analysis.

**6. A quoted `<<EOF` was read as a heredoc.** `echo "use <<EOF"` did the same thing. Heredocs are now recognised only outside quotes, and an unterminated one gets analysed as shell rather than trusted as data.

Five of the six are the same underlying mistake: **shell parsing is harder than it looks, and every shortcut is a bypass.** The sixth (the `-n` one) is a table entry that was too generous.

**7. On its first real use, the gate blocked its own write-up.** Installed, tested and replayed clean against 207 real commands, the gate then refused the commit-and-PR command that published this entry:

```
PreToolUse:Bash hook error: spend-gate: blocked `sky launch` -- it would launch paid cloud compute ...
```

The PR description was passed the usual way, `--body "$(cat <<'EOF' … EOF)"`, and its Markdown contained `` `bash -c "sky launch"` ``. In bash that text is inert: a heredoc with a quoted delimiter is literal, and here it sits inside `$(…)`. The gate got two things wrong. It thought the `<<'EOF'` was inside the double quotes, not seeing that `$(` resets quoting, so it never recognised the heredoc. Then it read the Markdown backticks as command substitution and "found" a launch. Nothing ran; a denied command is stopped whole. But this is exactly the failure that gets a gate switched off by lunchtime.

**The replay of 207 commands couldn't have caught it**, because none of those 207 had a spend command inside backticks inside a quoted heredoc. A replay only finds patterns that have already happened. The 208th command was the first of its kind.

**8. The mirror-image hole was in the same code.** Fixing 7 exposed the opposite case. A heredoc with an *unquoted* delimiter (`<<EOF`) is expanded by bash before the command sees it, so `cat <<EOF` with `$(sky launch x)` in the body really runs the launch. The gate had been dropping those bodies as plain data. Now quoted-delimiter bodies are data and unquoted-delimiter bodies have their substitutions analysed.

**9. A regex can't tell a string from code.** The re-run replay flagged `python3 test_spend_gate.py`, the documented command for running this gate's own tests, because the gate scanned the file for `sky.launch(` and the test file contains it *inside test strings*. The fix was to stop regexing Python and read it with Python's own parser (`ast`), which sees calls rather than text. As a side effect it closed a limitation I'd written down as accepted: `import sky as s; s.launch()` and `from sky import launch; launch()` are now caught. The regex had missed both.

**10. A chained call slipped through the new parser.** `boto3.client('ec2').run_instances(…)` calls a method on the *result* of a call. The name resolver gave up when a chain began with a call rather than a name. Found by the suite, fixed the same hour.

That's ten holes: six found before install, four after it went live, and each is now a regression case. None of the four post-install ones was a bypass. Two were false positives and two were misses the tests caught before any real command hit them. **The false positive is the one that matters most in practice.** A gate that blocks your commit messages doesn't get fixed; it gets deleted.

## What it does not do

This is the part to read before trusting it.

- **It's a policy check on an agent's commands, not a security boundary.** A base64-piped shell, a compiled binary, a script written in one call and run from a different path, or `getattr(sky, "launch")` and `importlib` tricks will all get past a command-string check. (Plain import aliases *are* caught, since Python is read with its own parser.) The hard boundary is two things: never giving the machine cloud credentials with spend authority, and provider-side billing caps. The gate catches the agent's ordinary, direct attempts, which is most of them, but it won't stop a determined adversary.
- **It doesn't estimate cost.** Above `$0` it asks a human rather than working out whether a launch fits the cap. The obvious next step is `sky launch --dryrun`, which prints `$/hr` per candidate. That has to wait for a cloud account to dry-run against.
- **It gates the Bash tool only.**

## What I would do differently

**Write the adversarial tests first.** All six holes came from sitting down to try to get past my own gate before installing it. Each one would have shipped if I'd tested only the obvious cases.

**Test against real work, not just invented cases, and don't trust either one alone.** The synthetic suite proves the gate blocks what it should. The replay of real commands shows it doesn't block what it shouldn't. Then the 208th real command was a false positive neither had seen, because a replay only covers patterns that have already happened. "0 false positives" is a statement about a sample, not a property of the gate.

**Parse the language, not the text.** Every Python false positive came from regexing source code, and switching to the real parser fixed that and caught more besides. The shell side can't use bash's own parser from Python, which is why most of the ten holes are on the shell side.

**Make the rehearsal the target.** The strongest acceptance test was having Claude, the agent the gate exists to constrain, try to spend money and fail, including with an evasion attempt.

## Acceptance check

| | Check | Result |
|---|---|---|
| A6b.1 | The gate blocks direct and wrapped paid-compute launches | pass: 53/53, including 12 regressions and 7 Python-parser cases |
| A6b.2 | The gate passes normal work and spend words that are only text | pass: 34/34 synthetic, and 0 false positives across 219 real commands, **after one live false positive was found and fixed** |
| A6b.3 | Fast enough to run before every shell command | pass: median 17 ms |
| A6b.4 | The agent it constrains tries to spend and is stopped, live | pass: direct and `bash -c` attempts both denied and logged |
| A6b.5 | Existing settings preserved; a documented way to turn it off | pass: merged, backed up, `/hooks` or delete one entry |
| A6b.6 | Limitations stated plainly | pass: see above |

Phase closed. [Phase 06a](README.md), cloud burst, stays deferred until there's something I want to spend on. When there is, the gate will already be in the way.
