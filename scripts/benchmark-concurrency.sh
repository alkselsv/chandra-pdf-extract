#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

if [ $# -lt 1 ]; then
  echo "Usage: $0 <pdf-path> [pages-spec]"
  echo "Example: $0 documents/Data1_2_2069_index.pdf 1-8"
  exit 1
fi

PDF_PATH="$1"
PAGES_SPEC="${2:-1-6}"

if [ ! -f "$PDF_PATH" ]; then
  echo "PDF not found: $PDF_PATH"
  exit 1
fi

CONCURRENCY_LIST="${CONCURRENCY_LIST:-1 2 3 4 6 8}"
BASE_OUT_DIR="${BASE_OUT_DIR:-outputs/bench_concurrency}"
PROMPT_TYPE="${PROMPT_TYPE:-ocr_layout}"
RENDER_SCALE="${RENDER_SCALE:-2.0}"
MAX_OUTPUT_TOKENS="${MAX_OUTPUT_TOKENS:-}"

mkdir -p "$BASE_OUT_DIR"
TS="$(date +%Y%m%d_%H%M%S)"
RESULTS_FILE="$BASE_OUT_DIR/results_${TS}.tsv"

echo -e "cs\telapsed_seconds\texit_code\tpages_spec\toutput_dir" > "$RESULTS_FILE"

echo "Benchmark start:"
echo "  pdf=$PDF_PATH"
echo "  pages=$PAGES_SPEC"
echo "  concurrency_list=$CONCURRENCY_LIST"
echo "  results_file=$RESULTS_FILE"
echo

for cs in $CONCURRENCY_LIST; do
  out_dir="$BASE_OUT_DIR/cs_${cs}_${TS}"
  cmd=(./.venv/bin/chandra-extract-pdf "$PDF_PATH" -p "$PAGES_SPEC" --output-dir "$out_dir" --prompt-type "$PROMPT_TYPE" --render-scale "$RENDER_SCALE" --concurrent-sequences "$cs")
  if [ -n "$MAX_OUTPUT_TOKENS" ]; then
    cmd+=(--max-output-tokens "$MAX_OUTPUT_TOKENS")
  fi

  echo "===== cs=$cs ====="
  start_s="$(date +%s)"
  set +e
  "${cmd[@]}"
  exit_code=$?
  set -e
  end_s="$(date +%s)"
  elapsed_s=$((end_s - start_s))

  printf "%s\t%s\t%s\t%s\t%s\n" "$cs" "$elapsed_s" "$exit_code" "$PAGES_SPEC" "$out_dir" >> "$RESULTS_FILE"
  echo "cs=$cs elapsed=${elapsed_s}s exit_code=$exit_code"
  echo
done

echo "Summary (sorted by elapsed_seconds):"
{
  head -n 1 "$RESULTS_FILE"
  tail -n +2 "$RESULTS_FILE" | sort -t$'\t' -k2,2n
} | column -t -s $'\t'

echo
echo "Saved: $RESULTS_FILE"
