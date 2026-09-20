#!/usr/bin/env python3
"""aimon -- one pane showing what the machine is doing while a model runs.

GNOME System Monitor has no GPU support at all, and even nvidia-smi does not
tell you the thing that matters most on this box: how much of the model is in
VRAM versus system RAM, which is what decides whether you get 45 tok/s or 5.

    python3 aimon.py [refresh_seconds]      live
    python3 aimon.py --once                 a single frame

Reads nvidia-smi, /proc, /sys and the local Ollama API. No root, no installs.
Ctrl+C to quit.
"""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

U = "http://127.0.0.1:11434"
ONCE = "--once" in sys.argv
args = [a for a in sys.argv[1:] if not a.startswith("-")]
REFRESH = float(args[0]) if args else 1.0
BULK_DEV = "sda"           # the disk the models live on

C = {"r": "\033[0m", "b": "\033[1m", "dim": "\033[2m",
     "g": "\033[32m", "y": "\033[33m", "red": "\033[31m", "cy": "\033[36m"}


def bar(frac, width=28, warn=0.85):
    frac = max(0.0, min(1.0, frac))
    filled = int(frac * width)
    color = C["red"] if frac >= warn else (C["y"] if frac >= 0.6 else C["g"])
    return color + "#" * filled + C["dim"] + "." * (width - filled) + C["r"]


def gpu():
    try:
        q = ("utilization.gpu,memory.used,memory.total,temperature.gpu,"
             "power.draw,clocks.current.graphics,name")
        out = subprocess.run(["nvidia-smi", "--query-gpu=" + q,
                              "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=5).stdout.strip()
        u, mu, mt, temp, pw, clk, name = [x.strip() for x in out.split(",")]
        return dict(util=float(u), used=float(mu), total=float(mt), temp=float(temp),
                    power=float(pw), clock=float(clk), name=name)
    except Exception:
        return None


def cpu_temp():
    best = 0.0
    for h in os.listdir("/sys/class/hwmon"):
        base = "/sys/class/hwmon/" + h
        try:
            if open(base + "/name").read().strip() != "k10temp":
                continue
            for f in os.listdir(base):
                if f.startswith("temp") and f.endswith("_input"):
                    best = max(best, int(open(base + "/" + f).read()) / 1000)
        except Exception:
            pass
    return best


def meminfo():
    m = {}
    for line in open("/proc/meminfo"):
        k, v = line.split(":", 1)
        m[k] = int(v.strip().split()[0]) / 1024 / 1024   # GiB
    return m


def disk_rate(prev):
    """MB/s read from the model disk -- shows weights paging in."""
    try:
        for line in open("/proc/diskstats"):
            f = line.split()
            if f[2] == BULK_DEV:
                sectors = int(f[5])
                now = time.time()
                rate = 0.0
                if prev[0] is not None:
                    dt = now - prev[1]
                    if dt > 0:
                        rate = (sectors - prev[0]) * 512 / 1e6 / dt
                prev[0], prev[1] = sectors, now
                return rate
    except Exception:
        pass
    return 0.0


def ollama():
    try:
        with urllib.request.urlopen(U + "/api/ps", timeout=2) as r:
            return json.load(r).get("models", [])
    except Exception:
        return None


def main():
    prev = [None, time.time()]
    print("\033[?25l", end="")          # hide cursor
    try:
        while True:
            w = shutil.get_terminal_size((100, 30)).columns
            g, m, ct = gpu(), meminfo(), cpu_temp()
            load = open("/proc/loadavg").read().split()[0]
            rate = disk_rate(prev)
            models = ollama()

            out = ["\033[H\033[J"]      # home + clear
            out.append(f"{C['b']}aimon{C['r']}  {time.strftime('%H:%M:%S')}"
                       f"{C['dim']}   refresh {REFRESH}s   Ctrl+C to quit{C['r']}\n")

            if g:
                vf = g["used"] / g["total"]
                out.append(f"{C['cy']}GPU{C['r']}  {g['name']}")
                out.append(f"  util  {bar(g['util']/100)} {g['util']:5.1f}%"
                           f"   {g['temp']:.0f}C  {g['power']:5.1f}W  {g['clock']:.0f}MHz")
                out.append(f"  VRAM  {bar(vf)} {g['used']/1024:5.1f} / {g['total']/1024:.1f} GiB")
            else:
                out.append(f"{C['red']}GPU  nvidia-smi unavailable{C['r']}")

            used = m["MemTotal"] - m["MemAvailable"]
            cache = m.get("Cached", 0)
            swap_used = m.get("SwapTotal", 0) - m.get("SwapFree", 0)
            out.append("")
            out.append(f"{C['cy']}CPU{C['r']}   load {load}   {ct:.0f}C")
            out.append(f"  RAM   {bar(used/m['MemTotal'])} {used:5.1f} / {m['MemTotal']:.0f} GiB"
                       f"   {C['dim']}cache {cache:.0f} GiB{C['r']}")
            if m.get("SwapTotal", 0):
                sf = swap_used / m["SwapTotal"]
                tag = f"  {C['red']}<- swapping, a model is too big{C['r']}" if sf > 0.1 else ""
                out.append(f"  swap  {bar(sf)} {swap_used:5.1f} / {m['SwapTotal']:.0f} GiB{tag}")
            out.append(f"  disk  {rate:6.0f} MB/s read from /dev/{BULK_DEV}"
                       + (f"   {C['y']}<- loading weights{C['r']}" if rate > 50 else ""))

            out.append("")
            if models is None:
                out.append(f"{C['red']}OLLAMA  endpoint not answering{C['r']}")
            elif not models:
                out.append(f"{C['dim']}OLLAMA  nothing loaded (keep-alive expired){C['r']}")
            else:
                out.append(f"{C['cy']}OLLAMA{C['r']}")
                for mm in models:
                    tot = mm.get("size", 0)
                    vram = mm.get("size_vram", 0)
                    pct = vram / tot * 100 if tot else 0
                    where = (f"{C['g']}fully in VRAM{C['r']}" if pct > 99 else
                             f"{C['y']}{pct:.0f}% VRAM / {100-pct:.0f}% RAM{C['r']}")
                    out.append(f"  {mm['name']:<28} {tot/1e9:5.1f} GB   {where}")
                    out.append(f"  {'':<28} {bar(pct/100, 28, warn=2)}")
            print("\n".join(line[:w + 20] for line in out), flush=True)
            if ONCE:                    # one frame, for scripting and for testing
                return
            time.sleep(REFRESH)
    except KeyboardInterrupt:
        pass
    finally:
        print("\033[?25h", end="")      # restore cursor


if __name__ == "__main__":
    main()
