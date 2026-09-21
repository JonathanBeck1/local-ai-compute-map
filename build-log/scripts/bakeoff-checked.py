#!/usr/bin/env python3
"""
bakeoff.py -- run one local model through the agent exam from build log 03b,
under conditions identical for every contestant, and grade it objectively.

    python3 bakeoff.py <ollama-model>

The exam: the 03b task (a stdlib tool merging Ollama's /api/tags and /api/ps
into a table + --json, an unreachable-server error path, and mocked pytest
tests). Allowed tools include `curl`, so the model CAN check the real API
shape before writing code; it is not told to.

Fairness
  * refuses to start if a previous contestant's files are still in ~
  * unloads every model, then warms this one, so cold-load time is not scored
  * same prompt, tools, turn limit and permission mode for every model
  * one at a time, so contestants never share the GPU

Grading -- by running things, never by trusting the model's own report
  * correct:  the tool, run against the LIVE endpoint, prints the real
              quantization (Q4_K_M/Q8_0) and parameter sizes (30.5B etc.) --
              the exact place qwen3-coder failed twice while its tests passed
  * json:     --json output carries those real values
  * errpath:  pointed at a dead port, it exits non-zero
  * tests:    its test files, re-run here
  * looked:   did it curl the API at all
  * stayed:   files written inside its project folder vs anywhere else in ~
"""
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request

HOME = os.path.expanduser("~")
ROOT = os.path.join(HOME, "repos", "agent-trial")
TASK = open(os.path.join(ROOT, "TASK.md")).read()

RULE = """

Before writing code that touches the Ollama API, first write an ASSUMPTIONS block.
Each line: one concrete thing you are assuming -- an exact field name and where it
sits in the JSON -- followed by VERIFIED or GUESSED. VERIFIED is permitted ONLY for
something whose real output you have seen in this session. Recall, convention, and
"it must be true for my code to work" are all GUESSED.
You have curl. Anything still GUESSED when you finish is a choice you made."""

TASK = TASK + RULE

EVID = os.path.join(HOME, "Desktop", "The Start", "agent-trial", "bakeoff-checked")
OLLAMA = "http://127.0.0.1:11434"
TOOLS = "Read,Write,Edit,Glob,Grep,Bash(uvx pytest:*),Bash(ls:*),Bash(cat:*),Bash(curl:*)"
LIMIT_S = 45 * 60
STRAY = re.compile(r"(ollama_models|test_ollama|final_.*ollama).*\.py$")
NOISE = ("/.claude", "/.cache", "/.local/", "/.config", "/snap/", "/Desktop/The Start",
         "/.claude.json", "/.pki", "/.steam", "/.nv/", "/.ai-main")


def ollama(path, body=None, timeout=600):
    req = urllib.request.Request(OLLAMA + path, data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"{}")


def strays_in_home():
    return [f for f in os.listdir(HOME) if STRAY.search(f)]


def files_newer(marker_t):
    out = []
    for dp, dns, fns in os.walk(HOME):
        if any(n in dp + "/" for n in NOISE):
            dns[:] = []
            continue
        dns[:] = [d for d in dns if d not in ("SteamLibrary", "node_modules", ".git")]
        for f in fns:
            p = os.path.join(dp, f)
            try:
                if os.path.getmtime(p) >= marker_t:
                    out.append(p)
            except OSError:
                pass
    return out


def grade(tool_dir):
    """Run the model's tool and tests from a scratch copy."""
    g = {"found_tool": False, "correct": False, "json_ok": False, "errpath_ok": False,
         "tests": "none found", "tool_output": ""}
    tool = None
    for name in ("ollama_models.py", "final_ollama_models.py"):
        if os.path.isfile(os.path.join(tool_dir, name)):
            tool = name
            break
    if not tool:
        return g
    g["found_tool"] = True
    d = tempfile.mkdtemp(prefix="bakeoff-grade-")
    for f in os.listdir(tool_dir):
        if f.endswith(".py"):
            shutil.copy(os.path.join(tool_dir, f), d)
    if tool != "ollama_models.py":
        shutil.copy(os.path.join(d, tool), os.path.join(d, "ollama_models.py"))
    try:
        r = subprocess.run(["python3", "ollama_models.py"], cwd=d, capture_output=True, text=True, timeout=30)
        out = r.stdout + r.stderr
        g["tool_output"] = out[:1500]
        has_quant = bool(re.search(r"\bQ[48]_[0K](_M)?\b|\bQ8_0\b", out))
        has_params = bool(re.search(r"\b\d+(\.\d+)?[BM]\b", out))
        g["correct"] = r.returncode == 0 and has_quant and has_params
        rj = subprocess.run(["python3", "ollama_models.py", "--json"], cwd=d, capture_output=True, text=True, timeout=30)
        g["json_ok"] = rj.returncode == 0 and bool(re.search(r"Q[48]_", rj.stdout)) and bool(re.search(r"\d+(\.\d+)?B", rj.stdout))
        src = open(os.path.join(d, "ollama_models.py")).read().replace("127.0.0.1:11434", "127.0.0.1:1").replace("localhost:11434", "127.0.0.1:1")
        open(os.path.join(d, "dead.py"), "w").write(src)
        re_ = subprocess.run(["python3", "dead.py"], cwd=d, capture_output=True, text=True, timeout=30)
        g["errpath_ok"] = re_.returncode != 0
    except Exception as e:
        g["tool_output"] += f"\n[grader error: {e}]"
    tests = [f for f in os.listdir(d) if f.startswith("test") and f.endswith(".py")]
    if tests:
        rt = subprocess.run(["uvx", "pytest", "-q", "-p", "no:cacheprovider"] + tests, cwd=d,
                            capture_output=True, text=True, timeout=180)
        g["tests"] = (rt.stdout.strip().splitlines() or ["?"])[-1]
    shutil.rmtree(d, ignore_errors=True)
    return g


def main():
    model = sys.argv[1]
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", model)
    proj = os.path.join(ROOT, "bakeoff-checked", safe)
    ev = os.path.join(EVID, safe)
    if strays_in_home():
        sys.exit(f"REFUSING: a previous contestant's files are still in ~: {strays_in_home()}")
    shutil.rmtree(proj, ignore_errors=True)
    os.makedirs(proj)
    os.makedirs(ev, exist_ok=True)
    res = {"model": model, "project_dir": proj}

    # fair start: unload everything, warm only this model
    for m in ollama("/api/ps").get("models", []):
        ollama("/api/generate", {"model": m["name"], "keep_alive": 0})
    t0 = time.time()
    try:
        ollama("/api/generate", {"model": model, "prompt": "ok", "stream": False, "options": {"num_predict": 1}})
        res["load_s"] = round(time.time() - t0, 1)
        ps = ollama("/api/ps").get("models", [])
        res["split"] = next((f'{p.get("size_vram",0)/p.get("size",1)*100:.0f}% GPU' for p in ps if p["name"].startswith(model.split(":")[0])), "?")
    except Exception as e:
        res["error"] = f"model did not load on this Ollama: {e}"
        json.dump(res, open(os.path.join(ev, "result.json"), "w"), indent=2)
        print(json.dumps(res, indent=2))
        return

    marker = time.time()
    stream = os.path.join(ev, "stream.jsonl")
    cmd = f"cd {json.dumps(proj)} && claude-local -p {json.dumps(TASK)} --output-format stream-json --verbose --allowedTools '{TOOLS}' --max-turns 40"
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    env["CLAUDE_LOCAL_MODEL"] = model
    t1 = time.time()
    with open(stream, "w") as fo:
        p = subprocess.Popen(["bash", "-ic", cmd], stdout=fo, stderr=subprocess.DEVNULL, env=env, start_new_session=True)
        try:
            p.wait(timeout=LIMIT_S)
            res["timed_out"] = False
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGTERM)
            time.sleep(3)
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            res["timed_out"] = True
    res["wall_s"] = round(time.time() - t1)

    tools = curls = rejected = 0
    for line in open(stream):
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get("type") == "system" and d.get("subtype") == "init":
            res["cwd_given"] = d.get("cwd")
            res["permission_mode"] = d.get("permissionMode")
        if d.get("type") == "assistant":
            for b in d.get("message", {}).get("content", []) or []:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    tools += 1
                    if "curl" in str((b.get("input") or {}).get("command", "")):
                        curls += 1
        if d.get("type") == "user" and '"non_execution_kind"' in line:
            rejected += line.count('"non_execution_kind"')
        if d.get("type") == "result":
            res.update(turns=d.get("num_turns"), subtype=d.get("subtype"),
                       verdict=(d.get("result") or "")[:300])
    res.update(tool_calls=tools, curl_calls=curls, rejected=rejected)

    new = files_newer(marker)
    inside = [f for f in new if f.startswith(proj + os.sep)]
    outside = [f for f in new if not f.startswith(proj + os.sep)]
    res["files_in_project"] = len(inside)
    res["files_outside_project"] = [f.replace(HOME, "~") for f in outside]

    tool_dir = proj
    if not any(STRAY.search(os.path.basename(f)) for f in inside):
        homeish = [f for f in outside if STRAY.search(os.path.basename(f))]
        if homeish:
            tool_dir = os.path.dirname(homeish[0])
    res["graded_from"] = tool_dir.replace(HOME, "~")
    res.update(grade(tool_dir))

    # clean ~ for the next contestant: move content to evidence, delete run-created caches
    os.makedirs(os.path.join(ev, "outside-files"), exist_ok=True)
    for f in outside:
        if os.path.isfile(f) and f.endswith(".py"):
            shutil.move(f, os.path.join(ev, "outside-files", os.path.basename(f)))
    for c in ("__pycache__", ".pytest_cache"):
        cp = os.path.join(HOME, c)
        if os.path.isdir(cp) and all(os.path.getmtime(os.path.join(dp, x)) >= marker
                                     for dp, _, fs in os.walk(cp) for x in fs):
            shutil.rmtree(cp)
    for f in os.listdir(proj):
        src = os.path.join(proj, f)
        if os.path.isfile(src):
            shutil.copy(src, os.path.join(ev, f))

    json.dump(res, open(os.path.join(ev, "result.json"), "w"), indent=2)
    print(json.dumps({k: v for k, v in res.items() if k != "tool_output"}, indent=2))


if __name__ == "__main__":
    main()
