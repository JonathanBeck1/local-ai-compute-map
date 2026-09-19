#!/usr/bin/env python3
"""
spend-gate -- a Claude Code PreToolUse hook that stops an agent launching paid
cloud compute.

The map this lab publishes concluded: "Agent-initiated cloud spend is the one
thing on this page nothing gates." Claude Code's own permission classifier has
no spend criterion. This is the gate.

How it decides
  Reads the Bash command Claude Code is about to run, works out which programs
  would actually execute, and checks them against a table of commands that
  provision paid compute (SkyPilot, RunPod, vast.ai, AWS, GCP, Azure, dstack,
  Modal, Terraform, Pulumi, and the Lambda/RunPod HTTP launch APIs).

  It follows what a shell would execute -- `bash -c`, `eval`, `$(...)`,
  backticks, `sudo`/`env`/`timeout`/`nohup` wrappers, `docker run ... sh -c`,
  heredocs fed to a shell or to Python, and scripts it is pointed at (one level
  deep) -- and it does NOT flag text that is only quoted, so
  `git commit -m "notes on sky launch"` and `grep "sky launch" notes.md` pass.

  `--dryrun` / `--dry-run` / `plan` / `preview` are allowed: they print a price
  or a diff without provisioning anything.

Budget
  ~/.config/spend-gate/config.json   {"monthly_cap_usd": 0}
  cap == 0 (or missing/unreadable)  -> deny. No agent may launch paid compute.
  cap  > 0                          -> ask. A human confirms each launch; this
                                       prompts even in auto mode.

What it does NOT do -- read this before trusting it
  * It is a policy check on an agent's commands, not a security boundary.
    Base64-piped shells, compiled binaries, a script written in one call and
    run from a different path, `getattr(sky, "launch")` or `importlib` tricks
    will get past a command-string check. (Plain import aliases -- `import sky
    as s`, `from sky import launch` -- ARE caught; Python is read with its own
    parser, which also means SDK names inside strings and comments are not
    mistaken for calls.) The hard boundary is not giving this machine cloud
    credentials with spend authority, plus provider-side billing caps.
  * It does not estimate cost yet. With a cap above zero it asks rather than
    computing whether a launch fits; `sky launch --dryrun` is the hook for that.
  * It gates the Bash tool only.

Every spend decision is appended to ~/.local/state/spend-gate/decisions.jsonl.
Fails open on non-spend commands if it ever crashes, so a bug cannot break the
shell -- but a crash on anything that still looks like spend is denied.
"""
import ast
import json
import os
import re
import shlex
import sys
import time

CONFIG = os.path.expanduser("~/.config/spend-gate/config.json")
LOG = os.path.expanduser("~/.local/state/spend-gate/decisions.jsonl")
MAX_DEPTH = 4
MAX_SCRIPT_BYTES = 1_000_000

# executable basename -> list of subcommand sequences that provision paid compute.
# A sequence matches if it appears contiguously among the non-flag tokens after
# the executable. A string starting with "~" is a regex for that one token.
SPEND = {
    "sky":       [["launch"], ["start"], ["jobs", "launch"], ["serve", "up"], ["serve", "update"]],
    "runpodctl": [["create"], ["start"]],
    "vastai":    [["create"], ["start"], ["launch"]],
    "aws":       [["ec2", "run-instances"], ["ec2", "start-instances"], ["ec2", "request-spot-instances"],
                  ["sagemaker", "~create-.*"], ["eks", "create-cluster"], ["eks", "create-nodegroup"]],
    "gcloud":    [["compute", "instances", "create"], ["compute", "instances", "start"],
                  ["compute", "tpus", "create"], ["compute", "tpus", "tpu-vm", "create"],
                  ["container", "clusters", "create"], ["ai", "custom-jobs", "create"]],
    "az":        [["vm", "create"], ["vm", "start"], ["ml", "compute", "create"], ["aks", "create"]],
    "dstack":    [["apply"], ["run"]],
    "modal":     [["run"], ["deploy"], ["serve"]],
    "terraform": [["apply"]],
    "tofu":      [["apply"]],
    "pulumi":    [["up"]],
}
# Tokens that make a matching segment harmless (price/diff only, nothing provisioned).
# Deliberately NOT "-n": `az vm create -n NAME` uses it for the resource name.
SAFE_FLAGS = {"--dryrun", "--dry-run"}
SEPARATORS = set(";&|()<>\n")

SHELLS = {"bash", "sh", "zsh", "dash", "ksh", "fish"}
PYTHONS = re.compile(r"^python(\d+(\.\d+)?)?$")

# HTTP launch endpoints, matched against a curl/wget/http segment's text.
HTTP_SPEND = re.compile(
    r"instance-operations/launch|podFindAndDeployOnDemand|podRentInterruptable"
    r"|vast\.ai/api/v0/asks/|api\.runpod\.io/graphql.*(deploy|rent)", re.I)

# SDK calls in Python source that provision compute.
PY_SPEND = re.compile(
    r"\bsky\.(launch|start|jobs\.launch|serve\.up)\s*\("
    r"|\brunpod\.create_pod\s*\("
    r"|\.run_instances\s*\("
    r"|\bsubprocess\.\w+\s*\(\s*\[\s*[\"']sky[\"']\s*,\s*[\"'](launch|start)[\"']"
    r"|\b(os\.system|os\.popen|subprocess\.\w+)\s*\(\s*[\"'][^\"']*\bsky\s+(launch|start|jobs\s+launch)\b")

# Conservative raw fallback, used only when the command cannot be parsed.
RAW_SPEND = re.compile(
    r"\bsky\s+(launch|start|jobs\s+launch|serve\s+up)\b|\brunpodctl\s+(create|start)\b"
    r"|\bvastai\s+(create|start)\b|\bec2\s+run-instances\b|\bcompute\s+instances\s+create\b"
    r"|\bvm\s+create\b|\bterraform\s+apply\b|\bpulumi\s+up\b|\bdstack\s+(apply|run)\b"
    r"|\bmodal\s+(run|deploy)\b|instance-operations/launch|podFindAndDeployOnDemand")


# Fully-qualified SDK calls that provision compute, after import aliases are resolved.
PY_SDK_SPEND = {"sky.launch", "sky.start", "sky.jobs.launch", "sky.serve.up", "runpod.create_pod"}
PY_SDK_SUFFIX = (".run_instances", ".create_instances", ".request_spot_instances")


def _dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    elif parts:
        # a method on an expression's result: boto3.client('ec2').run_instances(...)
        parts.append("?")
    else:
        return None
    return ".".join(reversed(parts))


def py_spend(src, depth):
    """Find compute-provisioning calls in Python source using the real parser:
    it sees calls, not text, so `sky.launch(` inside a string or comment (a test
    file, a docstring) does not match, while `import sky as s; s.launch()` and
    `from sky import launch; launch()` do. subprocess/os.system arguments are
    run through the shell analyser. Unparseable source falls back to the
    conservative regex."""
    try:
        tree = ast.parse(src)
    except Exception:
        m = PY_SPEND.search(src)
        return [m.group(0)] if m else []
    alias = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                alias[a.asname or a.name.split(".")[0]] = a.name if a.asname else a.name.split(".")[0]
        elif isinstance(n, ast.ImportFrom) and n.module:
            for a in n.names:
                alias[a.asname or a.name] = f"{n.module}.{a.name}"
    found = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        name = _dotted(n.func)
        if not name:
            continue
        head, _, tail = name.partition(".")
        full = alias.get(head, head) + ("." + tail if tail else "")
        if full in PY_SDK_SPEND or full.endswith(PY_SDK_SUFFIX):
            found.append(f"{full}()")
        elif full in ("os.system", "os.popen") or full.startswith("subprocess."):
            if n.args:
                a = n.args[0]
                text = None
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    text = a.value
                elif isinstance(a, (ast.List, ast.Tuple)):
                    text = " ".join(e.value for e in a.elts
                                    if isinstance(e, ast.Constant) and isinstance(e.value, str))
                if text:
                    sub = []
                    analyse(text, depth + 1, sub)
                    found.extend(h[1] for h in sub)
    return found


def load_cap():
    try:
        with open(CONFIG) as f:
            v = json.load(f).get("monthly_cap_usd", 0)
        return float(v) if float(v) > 0 else 0.0
    except Exception:
        return 0.0  # missing or broken config fails closed on spend


def log(entry):
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def base(tok):
    return os.path.basename(tok)


def matches_seq(nonflags, seq):
    n = len(seq)
    for i in range(len(nonflags) - n + 1):
        ok = True
        for want, got in zip(seq, nonflags[i:i + n]):
            if want.startswith("~"):
                if not re.fullmatch(want[1:], got):
                    ok = False
                    break
            elif want != got:
                ok = False
                break
        if ok:
            return True
    return False


def in_quotes(s, pos):
    """True if position `pos` in s falls inside a quoted string. A `$(` inside
    double quotes starts a command substitution where quoting resets, so
    `--body "$(cat <<'EOF'` puts that `<<` in shell context, not in a string.
    (Missing that made the gate block its own PR description.)"""
    stack, i, n = [], 0, len(s)
    while i < pos:
        c = s[i]
        top = stack[-1] if stack else None
        if top == "'":
            if c == "'":
                stack.pop()
            i += 1
            continue
        if c == "\\":
            i += 2
            continue
        if c == "$" and i + 1 < n and s[i + 1] == "(":
            stack.append("$(")
            i += 2
            continue
        if top == '"':
            if c == '"':
                stack.pop()
            i += 1
            continue
        if c == ")" and top == "$(":
            stack.pop()
        elif c in "'\"":
            stack.append(c)
        i += 1
    return bool(stack) and stack[-1] in ("'", '"')


HEREDOC = re.compile(
    r"(?<!<)<<(?!<)-?\s*"
    r"(?:(['\"])([A-Za-z_][A-Za-z0-9_]*)\1"   # <<'EOF' / <<"EOF"  -- quoted: body is literal
    r"|\\([A-Za-z_][A-Za-z0-9_]*)"            # <<\EOF             -- quoted: body is literal
    r"|([A-Za-z_][A-Za-z0-9_]*))")            # <<EOF              -- unquoted: $(...) and `...` in the body RUN


def strip_heredocs(cmd, depth, hits):
    """Remove heredoc bodies from the command text. Bodies fed to a shell are
    analysed as shell; bodies fed to Python are scanned for SDK calls; bodies
    fed to anything else (cat > file, git commit -F -) are plain text and
    dropped, which is what keeps commit messages from tripping the gate."""
    lines = cmd.split("\n")
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        m = None
        # `<<` only, never `<<<` (a here-string), and only outside quotes -- a
        # quoted "<<EOF" or a here-string misread as a heredoc would drop every
        # following line, hiding whatever comes after it.
        for cand in HEREDOC.finditer(line):
            if not in_quotes(line, cand.start()):
                m = cand
                break
        if not m:
            out.append(line)
            i += 1
            continue
        term = m.group(2) or m.group(3) or m.group(4)
        literal = bool(m.group(1) or m.group(3))
        body, j = [], i + 1
        while j < len(lines) and lines[j].strip() != term:
            body.append(lines[j])
            j += 1
        if j >= len(lines):
            # Never terminated: don't trust it as data. Analyse the rest as shell.
            out.append(line)
            i += 1
            continue
        head = line[:m.start()]
        try:
            head_toks = [base(t) for t in shlex.split(head, posix=True)]
        except ValueError:
            head_toks = [base(t) for t in head.split()]
        text = "\n".join(body)
        if any(t in SHELLS for t in head_toks):
            analyse(text, depth + 1, hits)
        elif any(PYTHONS.match(t) for t in head_toks):
            for f in py_spend(text, depth):
                hits.append(("python heredoc", f))
        elif not literal:
            # Unquoted delimiter: bash expands the body before handing it to the
            # command, so its $(...) and `...` really execute -- `cat <<EOF` with
            # `$(sky launch x)` inside launches. Analyse just those substitutions.
            for sub in re.findall(r"\$\(([^()]*)\)", text) + re.findall(r"`([^`]*)`", text):
                analyse(sub, depth + 1, hits)
        # quoted delimiter + non-shell command: the body is literal data, dropped
        out.append(head)
        i = j + 1
    return "\n".join(out)


def read_script(path):
    try:
        p = os.path.expanduser(path)
        if os.path.isfile(p) and os.path.getsize(p) <= MAX_SCRIPT_BYTES:
            with open(p, "r", errors="replace") as f:
                return f.read()
    except Exception:
        pass
    return None


def analyse_tokens(toks, depth, hits):
    if not toks:
        return
    for i, tok in enumerate(toks):
        b = base(tok)
        rest = toks[i + 1:]

        if b in SHELLS:
            for k, t in enumerate(rest):
                if t.startswith("-") and "c" in t.lstrip("-") and not t.startswith("--"):
                    if k + 1 < len(rest):
                        analyse(rest[k + 1], depth + 1, hits)
                    break
            else:
                for t in rest:
                    if not t.startswith("-"):
                        src = read_script(t)
                        if src is not None:
                            analyse(src, depth + 1, hits)
                        break

        elif b in ("eval",):
            analyse(" ".join(rest), depth + 1, hits)

        elif b in ("source", "."):
            if rest:
                src = read_script(rest[0])
                if src is not None:
                    analyse(src, depth + 1, hits)

        elif PYTHONS.match(b):
            if "-c" in rest and rest.index("-c") + 1 < len(rest):
                for f in py_spend(rest[rest.index("-c") + 1], depth):
                    hits.append(("python -c", f))
            if "-m" in rest and rest.index("-m") + 1 < len(rest) and rest[rest.index("-m") + 1].startswith("sky"):
                analyse_tokens(["sky"] + rest[rest.index("-m") + 2:], depth, hits)
            for t in rest:
                if t.endswith(".py"):
                    src = read_script(t)
                    if src:
                        for f in py_spend(src, depth):
                            hits.append((f"python {t}", f))

        elif b in ("curl", "wget", "http", "https", "xh"):
            hm = HTTP_SPEND.search(" ".join(rest))
            if hm:
                hits.append((b, hm.group(0)))

        elif b in SPEND and not any(t in SAFE_FLAGS for t in rest):
            nonflags = [t for t in rest if not t.startswith("-")]
            for seq in SPEND[b]:
                if matches_seq(nonflags, seq):
                    hits.append((b, " ".join([b] + [s.lstrip("~") for s in seq])))
                    break

    # A path executed directly (./run.sh, /opt/x/launch.sh) is scanned one level.
    first = toks[0]
    if ("/" in first) and base(first) not in SHELLS:
        src = read_script(first)
        if src is not None and src.startswith("#!"):
            analyse(src, depth + 1, hits)


def strip_comments(s):
    """Remove shell comments, quote-aware, keeping each newline. A `#` starts a
    comment only at the start of a word and outside quotes, so `${#arr}`,
    `"#tag"` and `don't` inside a comment are all handled. Keeping the newline
    matters: shlex's own comment handling eats it, which would merge the next
    line into this one and let `sky launch x # c` + a `--dryrun` line smuggle a
    real launch through the dry-run exemption."""
    out, i, n, q = [], 0, len(s), None
    while i < n:
        c = s[i]
        if q:
            out.append(c)
            if c == "\\" and q == '"' and i + 1 < n:
                out.append(s[i + 1])
                i += 2
                continue
            if c == q:
                q = None
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            out.append(c)
            out.append(s[i + 1])
            i += 2
            continue
        if c in "'\"":
            q = c
            out.append(c)
            i += 1
            continue
        if c == "#" and (i == 0 or s[i - 1] in " \t\n;&|()"):
            while i < n and s[i] != "\n":
                i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def analyse(cmd, depth, hits):
    if depth > MAX_DEPTH or not cmd:
        return
    cmd = strip_heredocs(cmd, depth, hits)
    cmd = strip_comments(cmd)
    cmd = cmd.replace("\\\n", " ")  # line continuation: `sky \<newline> launch`
    # Command substitutions run even inside double quotes; analyse them on their own.
    for sub in re.findall(r"\$\(([^()]*)\)", cmd) + re.findall(r"`([^`]*)`", cmd):
        analyse(sub, depth + 1, hits)
    lex = shlex.shlex(cmd, posix=True, punctuation_chars=";&|()<>\n")
    lex.whitespace = " \t\r"   # newline is a separator, not whitespace
    lex.whitespace_split = True
    lex.commenters = ""        # comments already stripped, quote-aware
    seg = []
    for tok in lex:  # may raise ValueError on unbalanced quotes
        if tok and set(tok) <= SEPARATORS:
            analyse_tokens(seg, depth, hits)
            seg = []
        else:
            seg.append(tok)
    analyse_tokens(seg, depth, hits)


def decide(command):
    hits = []
    try:
        analyse(command, 0, hits)
    except Exception:
        m = RAW_SPEND.search(command)
        if m:
            hits.append(("unparseable command, raw match", m.group(0)))
    return hits


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    hits = decide(command)
    if not hits:
        return 0  # no opinion: normal permission flow continues untouched

    cap = load_cap()
    what = "; ".join(sorted({h[1] for h in hits}))
    if cap <= 0:
        decision = "deny"
        reason = (f"spend-gate: blocked `{what}` -- it would launch paid cloud compute, and the "
                  f"monthly cap is $0 ({CONFIG}). Only the user can raise the cap. "
                  f"A `--dryrun` to see the price is allowed.")
    else:
        decision = "ask"
        reason = (f"spend-gate: `{what}` would launch paid cloud compute. Monthly cap is "
                  f"${cap:g}; this gate does not estimate cost yet, so a human must confirm.")

    log({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "decision": decision, "cap_usd": cap,
         "matched": [list(h) for h in hits], "command": command[:2000],
         "session": payload.get("session_id")})
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
        "permissionDecisionReason": reason,
    }}))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
