#!/usr/bin/env bash
# method2 — parallel Docker scrapers with live per-query progress
# Usage: ./run.sh [--concurrent N]   (default: 3)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUT_DIR="$SCRIPT_DIR/output"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$OUT_DIR" "$LOG_DIR"

MAX_CONCURRENT=3
[[ "$1" == "--concurrent" && -n "$2" ]] && MAX_CONCURRENT=$2

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

    echo "  $bn — ▶ launching..."
    MSYS_NO_PATHCONV=1 docker run --rm \
      -v gmaps-playwright-cache:/opt \
      -v "$f:/queries.txt:ro" \
      -v "$OUT_DIR:/out" \
      gosom/google-maps-scraper \
      -input /queries.txt \
      -results "/out/${bn}.csv" \
      -depth 20 \
      -c 4 \
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
