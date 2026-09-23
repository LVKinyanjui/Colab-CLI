#!/usr/bin/env bash
set -u

# Discover .blend files and run render_job.sh with a bounded concurrency.
# Usage:
#   render_scheduler.sh <blend_dir> <base_destination> [max_jobs]
#
# Example:
#   render_scheduler.sh blend /content/drive/MyDrive/code/outputs/blender 2

usage() {
    echo "Usage: $0 <blend_dir> <base_destination> [max_jobs]" >&2
    exit 2
}

[[ $# -le 3 ]] || usage

# Positional arguments override environment variables. This supports either:
#   ./render_scheduler.sh blend renders 2
# or:
#   BLEND_DIR=blend DEST=renders MAX_JOBS=2 ./render_scheduler.sh
BLEND_DIR=${1:-${BLEND_DIR:-blend}}
BASE_DEST=${2:-${DEST:-renders}}
MAX_JOBS=${3:-${MAX_JOBS:-2}}

if [[ ! -d "$BLEND_DIR" ]]; then
    echo "ERROR: blend directory not found: $BLEND_DIR" >&2
    exit 1
fi

if [[ ! "$MAX_JOBS" =~ ^[1-9][0-9]*$ ]]; then
    echo "ERROR: max_jobs must be a positive integer: $MAX_JOBS" >&2
    exit 2
fi

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
JOB_SCRIPT="$SCRIPT_DIR/render_job.sh"

if [[ ! -x "$JOB_SCRIPT" ]]; then
    echo "ERROR: render job script is missing or not executable: $JOB_SCRIPT" >&2
    exit 1
fi

# Resolve the blend directory once.
BLEND_DIR=$(readlink -f -- "$BLEND_DIR")

# Find direct children only. Null-delimited handling is used so filenames with
# spaces are safe; Blender job names should still ideally be simple shell-safe names.
mapfile -d '' BLEND_FILES < <(find "$BLEND_DIR" -maxdepth 1 -type f -name '*.blend' -print0 | sort -z)

if [[ ${#BLEND_FILES[@]} -eq 0 ]]; then
    echo "No .blend files found in: $BLEND_DIR"
    exit 0
fi

printf 'Render scheduler\n'
printf '  blend dir : %s\n' "$BLEND_DIR"
printf '  destination: %s\n' "$BASE_DEST"
printf '  max jobs  : %s\n' "$MAX_JOBS"
printf '  jobs found: %s\n' "${#BLEND_FILES[@]}"
printf '\n'

running=0
started=0
completed=0
failed=0

# Reap one completed child whenever the concurrency limit is reached.
reap_one() {
    if wait -n; then
        ((completed+=1))
    else
        ((completed+=1))
        ((failed+=1))
    fi
    ((running-=1))
}

for blend_file in "${BLEND_FILES[@]}"; do
    while (( running >= MAX_JOBS )); do
        reap_one
    done

    name=$(basename -- "$blend_file")
    name=${name%.blend}

    printf '[%s] launching %s (%s/%s)\n' \
        "$(date '+%F %T')" "$name" "$((started + 1))" "${#BLEND_FILES[@]}"

    "$JOB_SCRIPT" "$blend_file" "$BASE_DEST" &
    ((running+=1))
    ((started+=1))
done

# Wait for the remaining jobs.
while (( running > 0 )); do
    reap_one
done

printf '\n'
printf '[%s] scheduler complete\n' "$(date '+%F %T')"
printf '  total   : %s\n' "${#BLEND_FILES[@]}"
printf '  finished: %s\n' "$completed"
printf '  failed  : %s\n' "$failed"

if (( failed > 0 )); then
    exit 1
fi

exit 0
