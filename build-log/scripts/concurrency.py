#!/usr/bin/env python3
"""How well does ONE loaded model serve N agents at once?

The question behind a 256 GB Mac Studio purchase: load one large MoE, point
several coding agents at it. Does aggregate throughput scale with the number of
agents, or do they starve each other?

Method: fire N identical requests concurrently at a warm model, N = 1,2,4,8.
Record each request's own decode rate (what one agent feels) and the aggregate
rate (what the box delivers). Same prompt, same token budget, temperature 0.

    python3 concurrency.py <model> [ctx]

Two things this controls for:
  * the model is warmed first, so no cold-load time pollutes the result
  * every request asks for the same num_predict, so slow requests cannot be
    hidden by fast short ones
"""
import json
import sys
import threading
import time
import urllib.request

U = "http://127.0.0.1:11434"
MODEL = sys.argv[1]
CTX = int(sys.argv[2]) if len(sys.argv) > 2 else 8192
NPREDICT = 128
LEVELS = [1, 2, 4, 8]
PROMPT = ("You are reviewing a Python service. Explain, step by step, how to add "
          "retry logic with exponential backoff to an HTTP client, and what could go wrong.")


def post(body, timeout=1800):
    req = urllib.request.Request(U + "/api/generate", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def one(results, idx):
    t0 = time.time()
    try:
        d = post({"model": MODEL, "prompt": PROMPT, "stream": False,
                  "options": {"num_predict": NPREDICT, "temperature": 0, "num_ctx": CTX}})
        results[idx] = {
            "tok": d.get("eval_count", 0),
            "decode_s": d.get("eval_duration", 0) / 1e9,
            "prompt_tok": d.get("prompt_eval_count", 0),
            "prompt_s": d.get("prompt_eval_duration", 0) / 1e9,
            "wall": time.time() - t0,
        }
    except Exception as e:
        results[idx] = {"error": str(e)[:80], "wall": time.time() - t0}


print("  warming %s ..." % MODEL, flush=True)
post({"model": MODEL, "prompt": "hi", "stream": False,
      "options": {"num_predict": 8, "num_ctx": CTX}})

print("  %-3s %10s %12s %12s %10s %s" % ("N", "wall s", "per-agent", "aggregate", "scaling", "prompt tok/s"))
base = None
for n in LEVELS:
    results = [None] * n
    threads = [threading.Thread(target=one, args=(results, i)) for i in range(n)]
    t0 = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wall = time.time() - t0

    errs = [r for r in results if r and "error" in r]
    ok = [r for r in results if r and "error" not in r]
    if not ok:
        print("  %-3d  ALL FAILED: %s" % (n, errs[0]["error"]))
        continue
    per_agent = sum(r["tok"] / max(r["decode_s"], 1e-9) for r in ok) / len(ok)
    total_tok = sum(r["tok"] for r in ok)
    aggregate = total_tok / wall
    ptps = sum(r["prompt_tok"] / max(r["prompt_s"], 1e-9) for r in ok) / len(ok)
    if base is None:
        base = aggregate
    note = "  (%d failed)" % len(errs) if errs else ""
    print("  %-3d %10.1f %9.1f t/s %8.1f t/s %9.2fx %10.0f%s"
          % (n, wall, per_agent, aggregate, aggregate / base, ptps, note))
