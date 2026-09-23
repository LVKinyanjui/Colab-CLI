#!/usr/bin/env bash
set -u

# Render one Blender .blend file and archive completed PNG frames.
# Usage:
#   render_job.sh <blend_file> <base_destination>

usage() {
    echo "Usage: $0 <blend_file> <base_destination>" >&2
    exit 2
}

[[ $# -eq 2 ]] || usage

BLEND_FILE=$1
BASE_DEST=$2

BLENDER_BIN=${BLENDER_BIN:-blender}
CYCLES_DEVICE=${CYCLES_DEVICE:-CUDA+CPU}
MOVE_INTERVAL=${MOVE_INTERVAL:-10}
STABILITY_CHECK_SECONDS=${STABILITY_CHECK_SECONDS:-2}
WORK_ROOT=${WORK_ROOT:-/content/render_work}
LOG_DIR=${LOG_DIR:-$PWD/logs}
JOB_STATE_DIR=${JOB_STATE_DIR:-$PWD/.render_state}

if [[ ! -f "$BLEND_FILE" ]]; then
    echo "ERROR: blend file not found: $BLEND_FILE" >&2
    exit 1
fi

BLEND_FILE=$(readlink -f -- "$BLEND_FILE")
BLEND_BASENAME=$(basename -- "$BLEND_FILE")
NAME=${BLEND_BASENAME%.blend}

if [[ "$BASE_DEST" = /* ]]; then
    BASE_DEST=$(readlink -m -- "$BASE_DEST")
else
    BASE_DEST=$(readlink -m -- "$PWD/$BASE_DEST")
fi

DEST="$BASE_DEST/$NAME"
WORK_DIR="$WORK_ROOT/$NAME"

mkdir -p -- "$DEST" "$WORK_DIR" "$LOG_DIR" "$JOB_STATE_DIR"

BLENDER_LOG="$LOG_DIR/${NAME}.log"
MOVER_LOG="$LOG_DIR/${NAME}-mover.log"
JOB_PID_FILE="$JOB_STATE_DIR/job-${NAME}.pid"

printf '%s\n' '========================================'
printf 'Render job\n'
printf '  name : %s\n' "$NAME"
printf '  blend: %s\n' "$BLEND_FILE"
printf '  work : %s\n' "$WORK_DIR"
printf '  out  : %s\n' "$DEST"
printf '  log  : %s\n' "$BLENDER_LOG"
printf '%s\n' '========================================'

# Record this wrapper PID so the scheduler terminator can identify it.
printf '%s\n' "$$" >"$JOB_PID_FILE"

BLENDER_PID=""
MOVER_PID=""

cleanup() {
    local status=${1:-143}

    # Stop children first. This prevents the mover or Blender from surviving
    # after the render wrapper is terminated.
    if [[ -n "$MOVER_PID" ]] && kill -0 "$MOVER_PID" 2>/dev/null; then
        kill -TERM "$MOVER_PID" 2>/dev/null || true
    fi

    if [[ -n "$BLENDER_PID" ]] && kill -0 "$BLENDER_PID" 2>/dev/null; then
        kill -TERM "$BLENDER_PID" 2>/dev/null || true
    fi

    rm -f -- "$JOB_PID_FILE"
    exit "$status"
}

trap 'cleanup 143' TERM INT HUP

# Render into a job-specific directory so concurrent jobs cannot interfere.
# Blender stdout/stderr are completely redirected to the per-job log.
"$BLENDER_BIN" \
    -b "$BLEND_FILE" \
    -E CYCLES \
    -x 1 \
    -o "$WORK_DIR/$NAME" \
    -F PNG \
    --profile-gpu \
    -a \
    -- \
    --cycles-device "$CYCLES_DEVICE" \
    >"$BLENDER_LOG" 2>&1 &

BLENDER_PID=$!

# Start mover. A frame is moved only after its size is stable.
(
    printf '[%s] mover started for %s (Blender PID %s)\n' \
        "$(date '+%F %T')" "$NAME" "$BLENDER_PID"

    move_stable_frames() {
        local final=${1:-0}
        local f size1 size2

        for f in "$WORK_DIR"/"$NAME"*.png; do
            [[ -f "$f" ]] || continue

            size1=$(stat -c%s -- "$f" 2>/dev/null) || continue
            sleep "$STABILITY_CHECK_SECONDS"
            size2=$(stat -c%s -- "$f" 2>/dev/null) || continue

            if [[ "$size1" == "$size2" ]]; then
                if mv -- "$f" "$DEST/"; then
                    if [[ "$final" -eq 1 ]]; then
                        printf '[%s] final move: %s (%s bytes)\n' \
                            "$(date '+%F %T')" "$(basename -- "$f")" "$size2"
                    else
                        printf '[%s] moved %s (%s bytes)\n' \
                            "$(date '+%F %T')" "$(basename -- "$f")" "$size2"
                    fi
                else
                    printf '[%s] ERROR moving %s\n' \
                        "$(date '+%F %T')" "$f" >&2
                fi
            else
                printf '[%s] still writing: %s (%s -> %s bytes)\n' \
                    "$(date '+%F %T')" "$(basename -- "$f")" "$size1" "$size2"
            fi
        done
    }

    while kill -0 "$BLENDER_PID" 2>/dev/null; do
        printf '[%s] mover alive; checking for %s*.png\n' \
            "$(date '+%F %T')" "$NAME"
        move_stable_frames
        sleep "$MOVE_INTERVAL"
    done

    printf '[%s] Blender finished; final move pass\n' "$(date '+%F %T')"
    move_stable_frames 1
    printf '[%s] mover finished\n' "$(date '+%F %T')"
) >"$MOVER_LOG" 2>&1 &

MOVER_PID=$!

# If the scheduler terminates this wrapper, trap above cleans up both children.
wait "$BLENDER_PID"
BLENDER_STATUS=$?

wait "$MOVER_PID"
MOVER_STATUS=$?

rm -f -- "$JOB_PID_FILE"

printf '[%s] Blender exit status: %s\n' "$(date '+%F %T')" "$BLENDER_STATUS"
printf '[%s] mover exit status: %s\n' "$(date '+%F %T')" "$MOVER_STATUS"

if [[ "$BLENDER_STATUS" -ne 0 ]]; then
    printf '[%s] JOB FAILED: %s\n' "$(date '+%F %T')" "$NAME" >&2
    exit "$BLENDER_STATUS"
fi

if [[ "$MOVER_STATUS" -ne 0 ]]; then
    printf '[%s] JOB FAILED: mover error for %s\n' "$(date '+%F %T')" "$NAME" >&2
    exit "$MOVER_STATUS"
fi

printf '[%s] JOB COMPLETE: %s\n' "$(date '+%F %T')" "$NAME"
exit 0
