#!/usr/bin/env bash
# method2 — parallel Docker scrapers with live per-query progress
# Usage: ./run.sh [--concurrent N]   (default: 3)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUT_DIR="$SCRIPT_DIR/output"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$OUT_DIR" "$LOG_DIR"

IMAGE_NAME="${IMAGE_NAME:-gosom/google-maps-scraper:latest}"
MAX_CONCURRENT=4
[[ "$1" == "--concurrent" && -n "$2" ]] && MAX_CONCURRENT=$2

# Per-city geo coordinates for -fast-mode (approximate centers)
declare -A GEO
GEO[Ahmedabad]="23.0225,72.5714"
GEO[Bengaluru]="12.9716,77.5946"
GEO[Bhopal]="23.2599,77.4126"
GEO[Bhubaneswar]="20.2961,85.8245"
GEO[Bikaner]="28.0229,73.3119"
GEO[Bilaspur]="22.0797,82.1409"
GEO[Delhi]="28.7041,77.1025"
GEO[Goa]="15.4909,73.8278"
GEO[Gurugram]="28.4595,77.0266"
GEO[Hyderabad]="17.3850,78.4867"
GEO[Indore]="22.7196,75.8577"
GEO[Jaipur]="26.9124,75.7873"
GEO[Jodhpur]="26.2389,73.0243"
GEO[Kolkata]="22.5726,88.3639"
GEO[Lonavala]="18.7546,73.4062"
GEO[Lucknow]="26.8467,80.9462"
GEO[Mumbai]="19.0760,72.8777"
GEO[Nagpur]="21.1458,79.0882"
GEO[Noida]="28.5355,77.3910"
GEO[Patna]="25.5941,85.1376"
GEO[Pune]="18.5204,73.8567"
GEO[Raipur]="21.2514,81.6296"
GEO[Siliguri]="26.7271,88.3953"
GEO[Surat]="21.1702,72.8311"
GEO[Udaipur]="24.5854,73.7125"
GEO[Vadodara]="22.3072,73.1812"
GEO[Vapi]="20.3893,72.9106"

# Collect pending batches
BATCHES=("$SCRIPT_DIR"/batches/batch_*.txt)
TOTAL=${#BATCHES[@]}
PENDING=()
SKIPPED=0

echo "method2 — $TOTAL batches, --concurrent $MAX_CONCURRENT"
echo ""

for f in "${BATCHES[@]}"; do
  bn=$(basename "$f" .txt)
  csv="$OUT_DIR/${bn}.csv"
  if [[ -f "$csv" ]]; then
    rows=$(tail -n +2 "$csv" 2>/dev/null | wc -l)
    if [[ $rows -gt 0 ]]; then
      echo "  $bn — ✅ done ($rows leads)"
      ((SKIPPED++))
      continue
    fi
  fi
  PENDING+=("$f")
done

TOTAL_RUN=${#PENDING[@]}
echo "  $SKIPPED skipped, $TOTAL_RUN to run"
echo ""

if [[ $TOTAL_RUN -eq 0 ]]; then
  echo "═══════════════════════════════════════"
  echo "  ALL DONE — $TOTAL batches"
  total=0
  for f in "$OUT_DIR"/*.csv; do
    r=$(tail -n +2 "$f" 2>/dev/null | wc -l)
    total=$((total + r))
  done
  echo "  Total leads: $total"
  exit 0
fi

# Pre-create empty CSVs so gosom can open them for writing
for f in "${PENDING[@]}"; do
  bn=$(basename "$f" .txt)
  > "$OUT_DIR/${bn}.csv"
done

# Launch containers in waves
IDX=0
declare -A DPIDS

while [[ $IDX -lt $TOTAL_RUN ]]; do
  while [[ ${#DPIDS[@]} -lt $MAX_CONCURRENT && $IDX -lt $TOTAL_RUN ]]; do
    f="${PENDING[$IDX]}"
    bn=$(basename "$f" .txt)
    log="$LOG_DIR/${bn}.log"
    csv="$OUT_DIR/${bn}.csv"

    city="${bn##*_}"
    geo="${GEO[$city]:-23.2599,77.4126}"
    echo "  $bn — ▶ launching... (geo: $geo)"
    MSYS_NO_PATHCONV=1 docker run --rm \
      -v gmaps-playwright-cache:/opt \
      -v "$f:/queries.txt:ro" \
      -v "$OUT_DIR:/out" \
      "$IMAGE_NAME" \
      -input /queries.txt \
      -results "/out/${bn}.csv" \
      -depth 60 \
      -fast-mode \
      -geo "$geo" \
      -c 12 \
      -exit-on-inactivity 3m > "$log" 2>&1 &
    DPIDS["$bn"]=$!
    ((IDX++))
  done

  # Poll all running containers every 5s, report finished ones
  while [[ ${#DPIDS[@]} -gt 0 ]]; do
    for bn in "${!DPIDS[@]}"; do
      if ! kill -0 "${DPIDS[$bn]}" 2>/dev/null; then
        wait "${DPIDS[$bn]}" 2>/dev/null
        unset DPIDS["$bn"]
        rows=$(tail -n +2 "$OUT_DIR/${bn}.csv" 2>/dev/null | wc -l)
        echo "  $bn — ✅ done ($rows leads)"
        break
      fi
    done
    [[ ${#DPIDS[@]} -gt 0 ]] && sleep 5
  done
done

echo ""
echo "═══════════════════════════════════════"
echo "  ALL DONE — $TOTAL batches"
total=0
for f in "$OUT_DIR"/*.csv; do
  r=$(tail -n +2 "$f" 2>/dev/null | wc -l)
  total=$((total + r))
done
echo "  Total leads: $total"
