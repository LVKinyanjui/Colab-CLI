#!/usr/bin/env bash
set -u

# Discover .blend files and run render_job.sh with bounded concurrency.
# Usage:
#   render_scheduler.sh [--frame FRAME | --animation] [blend_dir] [base_destination] [max_jobs]
#
# Default: render the full animation (-a).

usage() {
    echo "Usage: $0 [--frame FRAME | --animation] [blend_dir] [base_destination] [max_jobs]" >&2
    exit 2
}

RENDER_ARGS=()
if [[ ${1:-} == "--frame" ]]; then
    [[ $# -ge 2 ]] || usage
    [[ ${2:-} =~ ^-?[0-9]+$ ]] || {
        echo "ERROR: --frame requires an integer frame number: ${2:-}" >&2
        exit 2
    }
    RENDER_ARGS=(--frame "$2")
    shift 2
elif [[ ${1:-} == "--animation" ]]; then
    RENDER_ARGS=(--animation)
    shift
fi

[[ $# -le 3 ]] || usage

BLEND_DIR=${1:-${BLEND_DIR:-blend}}
BASE_DEST=${2:-${DEST:-renders}}
MAX_JOBS=${3:-${MAX_JOBS:-2}}
JOB_STATE_DIR=${JOB_STATE_DIR:-$PWD/.render_state}

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

BLEND_DIR=$(readlink -f -- "$BLEND_DIR")
mkdir -p -- "$JOB_STATE_DIR"
SCHEDULER_PID_FILE="$JOB_STATE_DIR/scheduler.pid"

mapfile -d '' BLEND_FILES < <(find "$BLEND_DIR" -maxdepth 1 -type f -name '*.blend' -print0 | sort -z)

if [[ ${#BLEND_FILES[@]} -eq 0 ]]; then
    echo "No .blend files found in: $BLEND_DIR"
    exit 0
fi

printf 'Render scheduler\n'
printf '  blend dir : %s\n' "$BLEND_DIR"
printf '  destination: %s\n' "$BASE_DEST"
printf '  max jobs  : %s\n' "$MAX_JOBS"
if [[ ${RENDER_ARGS[0]:-} == "--frame" ]]; then
    printf '  render    : frame %s\n' "${RENDER_ARGS[1]}"
else
    printf '  render    : animation (-a)\n'
fi
printf '  jobs found: %s\n' "${#BLEND_FILES[@]}"
printf '\n'

printf '%s\n' "$$" >"$SCHEDULER_PID_FILE"

running=0
started=0
completed=0
failed=0
shutdown_requested=0

# Keep a list of currently active render_job wrapper PIDs.
declare -a JOB_PIDS=()

action_kill_jobs() {
    local pid
    for pid in "${JOB_PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill -TERM "$pid" 2>/dev/null || true
        fi
    done
}

scheduler_shutdown() {
    shutdown_requested=1
    printf '\n[%s] scheduler shutdown requested; stopping active jobs\n' \
        "$(date '+%F %T')" >&2
    action_kill_jobs
}

trap scheduler_shutdown TERM INT HUP

# Bash 5.1+ wait -n -p is ideal here, but plain wait -n keeps compatibility.
reap_one() {
    local before=${#JOB_PIDS[@]}
    local pid
    local idx

    if (( before == 0 )); then
        return
    fi

    if wait -n; then
        ((completed+=1))
    else
        ((completed+=1))
        ((failed+=1))
    fi
    ((running-=1))

    # Remove completed PIDs by probing the list. A dead PID is safe to remove.
    local -a remaining=()
    for pid in "${JOB_PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            remaining+=("$pid")
        fi
    done
    JOB_PIDS=("${remaining[@]}")
}

for blend_file in "${BLEND_FILES[@]}"; do
    (( shutdown_requested )) && break

    while (( running >= MAX_JOBS )); do
        reap_one
        (( shutdown_requested )) && break
    done

    (( shutdown_requested )) && break

    name=$(basename -- "$blend_file")
    name=${name%.blend}

    printf '[%s] launching %s (%s/%s)\n' \
        "$(date '+%F %T')" "$name" "$((started + 1))" "${#BLEND_FILES[@]}"

    JOB_STATE_DIR="$JOB_STATE_DIR" "$JOB_SCRIPT" "${RENDER_ARGS[@]}" "$blend_file" "$BASE_DEST" &
    pid=$!
    JOB_PIDS+=("$pid")
    ((running+=1))
    ((started+=1))
done

while (( running > 0 )); do
    reap_one
done

rm -f -- "$SCHEDULER_PID_FILE"

if (( shutdown_requested )); then
    printf '[%s] scheduler stopped\n' "$(date '+%F %T')"
    exit 143
fi

printf '\n'
printf '[%s] scheduler complete\n' "$(date '+%F %T')"
printf '  total   : %s\n' "${#BLEND_FILES[@]}"
printf '  started : %s\n' "$started"
printf '  finished: %s\n' "$completed"
printf '  failed  : %s\n' "$failed"

if (( failed > 0 )); then
    exit 1
fi

exit 0
