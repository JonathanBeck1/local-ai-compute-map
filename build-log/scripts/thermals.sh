#!/usr/bin/env bash
# thermals.sh -- sample every temperature this machine exposes, print a compact
# line, and say loudly if anything crosses a threshold.
#
#   bash thermals.sh          # one sample
#   bash thermals.sh 20 30    # 20 samples, 30s apart
#
# Thresholds are deliberately well under the throttle points: the 5900XT
# throttles near 95 C and the 4070 near 83-88 C, so these leave real margin.
# Exits non-zero the moment something is over, so a caller can stop the work.

CPU_MAX=85; GPU_MAX=80; NVME_MAX=70; DIMM_MAX=75; COOLANT_MAX=45

read_all() {
    CPU=0; DIMM=0; NVME=0; COOLANT=0
    for h in /sys/class/hwmon/hwmon*; do
        name=$(cat "$h/name" 2>/dev/null)
        for t in "$h"/temp*_input; do
            [ -f "$t" ] || continue
            v=$(awk '{printf "%.0f", $1/1000}' "$t" 2>/dev/null) || continue
            case "$name" in
                k10temp)    [ "$v" -gt "$CPU" ] && CPU=$v ;;
                jc42)       [ "$v" -gt "$DIMM" ] && DIMM=$v ;;
                nvme)       [ "$v" -gt "$NVME" ] && NVME=$v ;;
                kraken2023) [ "$v" -gt "$COOLANT" ] && COOLANT=$v ;;
            esac
        done
    done
    GPU=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader 2>/dev/null | head -1)
    PWR=$(nvidia-smi --query-gpu=power.draw --format=csv,noheader 2>/dev/null | head -1)
    LOAD=$(awk '{print $1}' /proc/loadavg)
}

check() {
    bad=""
    [ "${CPU:-0}" -ge "$CPU_MAX" ] && bad="$bad CPU=${CPU}C"
    [ "${GPU:-0}" -ge "$GPU_MAX" ] && bad="$bad GPU=${GPU}C"
    [ "${NVME:-0}" -ge "$NVME_MAX" ] && bad="$bad NVMe=${NVME}C"
    [ "${DIMM:-0}" -ge "$DIMM_MAX" ] && bad="$bad DIMM=${DIMM}C"
    [ "${COOLANT:-0}" -ge "$COOLANT_MAX" ] && bad="$bad coolant=${COOLANT}C"
    printf '  %s  CPU %2sC | GPU %2sC (%s) | DIMM %2sC | NVMe %2sC | coolant %2sC | load %s\n' \
        "$(date +%H:%M:%S)" "$CPU" "$GPU" "$PWR" "$DIMM" "$NVME" "$COOLANT" "$LOAD"
    if [ -n "$bad" ]; then
        echo "  *** OVER THRESHOLD:$bad -- stopping the run ***"
        return 1
    fi
    return 0
}

N=${1:-1}; GAP=${2:-30}
for i in $(seq 1 "$N"); do
    read_all
    check || exit 1
    if [ "$i" -lt "$N" ]; then sleep "$GAP"; fi
done
exit 0   # otherwise the loop's last test becomes the script's exit status
