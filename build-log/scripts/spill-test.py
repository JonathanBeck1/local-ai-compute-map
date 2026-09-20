#!/usr/bin/env python3
"""What does spilling out of VRAM actually cost — dense vs MoE?

Ollama places whole LAYERS on the GPU, in order, at load time. `num_gpu` sets
how many. So forcing a model that fits to use fewer GPU layers simulates being
too big for the card, with everything else held constant.

Dense: every parameter is read for every token, so whatever sits in RAM is read
over the DDR4 bus every single token.
MoE: only a few experts per token are read, so most of what sits in RAM is not
touched for any given token.

That difference is the whole reason a 30B MoE is usable here and a 30B dense
model would not be. This measures it instead of asserting it.

    python3 spill.py <model> <ctx> <n_gpu_layers,...>
"""
import json
import sys
import time
import urllib.request

U = "http://127.0.0.1:11434"
MODEL = sys.argv[1]
CTX = int(sys.argv[2])
LAYERS = [int(x) for x in sys.argv[3].split(",")]


def post(path, body, timeout=1800):
    req = urllib.request.Request(U + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"{}")


def unload_all():
    for m in post("/api/ps", {}) .get("models", []) if False else json.loads(
            urllib.request.urlopen(U + "/api/ps", timeout=30).read()).get("models", []):
        post("/api/generate", {"model": m["name"], "keep_alive": 0})
    time.sleep(3)


print("  %-8s %8s %10s %12s" % ("n_gpu", "tok/s", "in VRAM", "vs baseline"))
base = None
for n in LAYERS:
    # -1 means "let Ollama decide", which is the only option for a model whose
    # full layer set will not fit: asking for all of them returns a CUDA OOM.
    label = "auto" if n < 0 else str(n)
    unload_all()
    # Weights are mmap'd and fault in from disk DURING the first generation, not
    # during load_duration. Without this warm-up the first measurement is
    # disk-bound and can even rank fewer GPU layers as faster. Discard it.
    post("/api/generate", {
        "model": MODEL, "prompt": "warm", "stream": False,
        "options": {"num_predict": 8, "temperature": 0, "num_ctx": CTX, "num_gpu": n},
    })
    d = post("/api/generate", {
        "model": MODEL,
        "prompt": "Write a Python function that reverses a linked list.",
        "stream": False,
        "options": {"num_predict": 96, "temperature": 0, "num_ctx": CTX, "num_gpu": n},
    })
    tps = d["eval_count"] / (d["eval_duration"] / 1e9)
    ps = json.loads(urllib.request.urlopen(U + "/api/ps", timeout=30).read()).get("models", [])
    pct = 0.0
    for m in ps:
        if m["name"].split(":")[0] == MODEL.split(":")[0]:
            pct = m.get("size_vram", 0) / max(m.get("size", 1), 1) * 100
    if base is None:
        base = tps
    print("  %-8s %8.1f %9.0f%% %11.2fx" % (label, tps, pct, tps / base))
unload_all()
