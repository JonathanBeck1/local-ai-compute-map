#!/usr/bin/env python3
"""Can this machine run a 70B model? Calibrate on measured points, then predict.

Generation on this box is bandwidth-bound: per token you read some bytes from
VRAM at ~504 GB/s and the rest from DDR4. Dense reads every weight; an MoE
reads only its active experts. So:

    seconds/token = bytes_read * f / BW_gpu  +  bytes_read * (1-f) / BW_ram

The only free parameter is the effective DDR4 bandwidth, and it is not guessed:
it falls out of the pure-CPU measurement (gemma4 at num_gpu=0).

Everything in MEASURED is a number produced on this machine today.
"""
BW_GPU = 504.0          # RTX 4070, spec
Q4_BYTES_PER_PARAM = 0.58   # observed: 30.5B model -> 18.6 GB on disk

# model, GB actually read per token, fraction resident in VRAM, measured tok/s
MEASURED = [
    ("gemma4:12b dense, CPU only",   7.6,  0.00,  5.8),
    ("gemma4:12b dense, 30% on GPU", 7.6,  0.30,  8.3),
    ("gemma4:12b dense, 49% on GPU", 7.6,  0.49, 11.3),
    ("gemma4:12b dense, all on GPU", 7.6,  1.00, 55.7),
    ("qwen3.5:27b dense, 51% on GPU", 17.0, 0.51, 4.8),
    ("qwen3-coder:30b MoE (~3B act)", 3.0 * Q4_BYTES_PER_PARAM, 0.49, 45.1),
    ("qwen3.5:122b MoE (~10B act)",  10.0 * Q4_BYTES_PER_PARAM, 0.12, 8.66),
]

# Calibrate DDR4 from the one point with zero GPU involvement.
name, gb, f, tps = MEASURED[0]
BW_RAM = gb * tps
print("  calibration: %s -> %.1f GB/token x %.1f tok/s = %.0f GB/s effective DDR4" % (name, gb, tps, BW_RAM))
print("  (theoretical dual-channel DDR4-3200 is 51.2 GB/s, so this is ~%.0f%% of spec)\n" % (BW_RAM / 51.2 * 100))


def predict(gb_read, f):
    return 1.0 / (gb_read * f / BW_GPU + gb_read * (1 - f) / BW_RAM)


print("  %-34s %10s %10s %8s" % ("measured point", "predicted", "measured", "error"))
for name, gb, f, tps in MEASURED:
    p = predict(gb, f)
    print("  %-34s %8.1f   %8.1f   %6.0f%%" % (name, p, tps, (p - tps) / tps * 100))

print("\n  --- now the question: a 70B model, Q4 ~40 GB of weights ---")
for ctx, vram_for_weights in (("4k context", 10.5), ("64k context", 7.0)):
    f = vram_for_weights / 40.0
    p = predict(40.0, f)
    print("  70B DENSE, %-12s %4.1f GB of 40 on the GPU (%.0f%%) -> %5.2f tok/s  (%.0f s for a 60-token reply)"
          % (ctx, vram_for_weights, f * 100, p, 60 / p))

for act, label in ((3.0, "70B-A3B"), (6.0, "70B-A6B")):
    gb = act * Q4_BYTES_PER_PARAM
    f = 10.5 / 40.0
    p = predict(gb, f)
    print("  %s MoE, if one existed:  %.1f GB read/token          -> %5.1f tok/s  (%.0f s for a 60-token reply)"
          % (label, gb, p, 60 / p))
