#!/usr/bin/env python3
"""Does an 8-bit KV cache damage long-context recall?

The speed win from OLLAMA_KV_CACHE_TYPE=q8_0 is only worth taking if the model
can still find a fact buried in a long prompt -- which is the whole reason this
endpoint runs at 64k. So: bury a unique fact at several depths in a long
document, ask for it, and check the answer exactly. Same prompts, same seed,
same model, run once per KV setting.

    python3 needle.py <label> [target_tokens]

Notes on honesty:
  * every run uses a FRESH random code, so a correct answer cannot come from a
    cached response or from the model having seen the code earlier
  * the filler is varied prose, not one repeated sentence -- repeated text
    compresses in ways that make retrieval unrealistically easy
  * prompt tok/s is recorded too, since that is the other number that matters
    for agent work at 64k and has never been measured here
"""
import json
import random
import sys
import time
import urllib.request

U = "http://127.0.0.1:11434"
MODEL = "qwen3-coder:30b"
LABEL = sys.argv[1]
TARGET_TOKENS = int(sys.argv[2]) if len(sys.argv) > 2 else 32000
DEPTHS = [0.05, 0.5, 0.95]

TOPICS = [
    "The maintenance crew logged routine checks on the ventilation system.",
    "Quarterly figures for the northern depot arrived later than scheduled.",
    "Rainfall that week stayed below the seasonal average across the valley.",
    "The archive catalogue lists every shipment by date and container number.",
    "Staff rotations were adjusted after the timetable review in spring.",
    "Signal strength along the coastal relay varied with the tide.",
    "The inventory of spare parts was reconciled against the supplier ledger.",
    "Attendance at the regional briefing fell short of the room's capacity.",
    "Soil samples from the eastern plots were sent for laboratory analysis.",
    "The fleet's fuel consumption was tracked per route rather than per vehicle.",
]


def post(path, body, timeout=1800):
    req = urllib.request.Request(U + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"{}")


def filler(n_words, rng):
    return " ".join(rng.choice(TOPICS) for _ in range(n_words // 9))


NEGATIVE = "--negative" in sys.argv   # omit the needle: a FOUND here means the test is broken


def run_one(depth, rng):
    code = "%d-%s" % (rng.randint(1000, 9999), rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ") * 3)
    needle = f"IMPORTANT RECORD: the access code for the Harbour vault is {code}."
    words = int(TARGET_TOKENS * 0.75)
    before, after = int(words * depth), int(words * (1 - depth))
    if NEGATIVE:
        doc = filler(before, rng) + "\n\n" + filler(after, rng)
    else:
        doc = filler(before, rng) + "\n\n" + needle + "\n\n" + filler(after, rng)
    prompt = (doc + "\n\nQuestion: what is the access code for the Harbour vault? "
              "Answer with the code only, nothing else.")
    t0 = time.time()
    d = post("/api/generate", {
        "model": MODEL, "prompt": prompt, "stream": False,
        "options": {"num_predict": 32, "temperature": 0, "seed": 42, "num_ctx": 65536},
    })
    ans = (d.get("response") or "").strip()
    ok = code in ans
    ptoks = d.get("prompt_eval_count", 0)
    pdur = d.get("prompt_eval_duration", 1) / 1e9
    print("  depth %3d%%  prompt %6d tok at %6.0f tok/s  |  %s  |  wanted %s got %r" % (
        int(depth * 100), ptoks, ptoks / max(pdur, 0.001),
        "FOUND" if ok else "MISS ", code, ans[:40]))
    return ok, time.time() - t0


if __name__ == "__main__":
    rng = random.Random(20260919)
    print(f"=== {LABEL}: needle-in-haystack, ~{TARGET_TOKENS} tokens, {MODEL} ===")
    hits = 0
    for d in DEPTHS:
        ok, _ = run_one(d, rng)
        hits += ok
    print(f"  {LABEL}: {hits}/{len(DEPTHS)} found")
