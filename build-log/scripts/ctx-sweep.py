#!/usr/bin/env python3
"""Does the 64k context setting cost throughput on the 30B MoE?

For each context size: unload everything, load the model at that num_ctx,
generate 128 tokens, and record tok/s together with how much of the model
actually ended up in VRAM. Same model, same prompt, same GPU state each time.
"""
import json
import sys
import time
import urllib.request

U = "http://127.0.0.1:11434"
MODEL = sys.argv[1] if len(sys.argv) > 1 else "qwen3-coder:30b"
SIZES = [int(x) for x in (sys.argv[2].split(",") if len(sys.argv) > 2 else ["8192", "32768", "65536"])]


def get(path, body=None, timeout=900):
    req = urllib.request.Request(
        U + path, data=json.dumps(body).encode() if body else None,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"{}")


def unload_all():
    for m in get("/api/ps").get("models", []):
        get("/api/generate", {"model": m["name"], "keep_alive": 0})
    time.sleep(4)


print("  ctx      tok/s   in VRAM   loaded size   load")
for n in SIZES:
    unload_all()
    d = get("/api/generate", {
        "model": MODEL,
        "prompt": "Write a Python function that reverses a linked list.",
        "stream": False,
        "options": {"num_predict": 128, "temperature": 0, "num_ctx": n},
    })
    tps = d["eval_count"] / (d["eval_duration"] / 1e9)
    ps = get("/api/ps").get("models", [])
    pct, size = 0.0, 0.0
    for m in ps:
        if m["name"] == MODEL:
            pct = m.get("size_vram", 0) / max(m.get("size", 1), 1) * 100
            size = m["size"] / 1e9
    print("  %-7d  %5.1f   %5.0f%%   %7.1f GB   %4.1fs" % (n, tps, pct, size, d.get("load_duration", 0) / 1e9))

unload_all()
