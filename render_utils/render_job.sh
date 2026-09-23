#!/usr/bin/env bash
set -u

# Render one Blender .blend file and archive completed PNG frames.
# Usage:
#   render_job.sh [--frame FRAME | --animation] <blend_file> <base_destination>

usage() {
    echo "Usage: $0 [--frame FRAME | --animation] <blend_file> <base_destination>" >&2
    exit 2
}

RENDER_MODE=animation
FRAME=""

if [[ ${1:-} == "--frame" ]]; then
    [[ $# -eq 4 ]] || usage
    [[ ${2:-} =~ ^-?[0-9]+$ ]] || {
        echo "ERROR: --frame requires an integer frame number: ${2:-}" >&2
        exit 2
    }
    RENDER_MODE=frame
    FRAME=$2
    shift 2
elif [[ ${1:-} == "--animation" ]]; then
    [[ $# -eq 3 ]] || usage
    shift
elif [[ $# -ne 2 ]]; then
    usage
fi

BLEND_FILE=$1
BASE_DEST=$2

# ---------------------------------------------------------------------------
# Extensible Configuration (Environment Overrides with Defaults)
# ---------------------------------------------------------------------------
BLENDER_BIN=${BLENDER_BIN:-blender}
RENDER_ENGINE=${RENDER_ENGINE:-CYCLES}
CYCLES_DEVICE=${CYCLES_DEVICE:-CUDA+CPU}
MOVE_INTERVAL=${MOVE_INTERVAL:-10}
STABILITY_CHECK_SECONDS=${STABILITY_CHECK_SECONDS:-2}
WORK_ROOT=${WORK_ROOT:-/content/render_work}
LOG_DIR=${LOG_DIR:-$PWD/logs}
JOB_STATE_DIR=${JOB_STATE_DIR:-$PWD/.render_state}

# Setup script extension points
SETUP_SCRIPT=${SETUP_SCRIPT:-}          # Path to .py script, e.g. set_cycles_performance.py
SETUP_ARGS=${SETUP_ARGS:-}              # Flags passed to setup script after '--'
BLENDER_EXTRA_ARGS=${BLENDER_EXTRA_ARGS:-} # Extra flags passed to blender before '--'

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

# ---------------------------------------------------------------------------
# Build the Modular Blender Command
# ---------------------------------------------------------------------------
declare -a CMD_BEFORE_DASH=()
declare -a CMD_AFTER_DASH=()

# 1. Base required flags
CMD_BEFORE_DASH+=(
    "$BLENDER_BIN"
    -b "$BLEND_FILE"
)

# 2. Engine (optional: can be omitted if script or .blend controls it)
if [[ -n "$RENDER_ENGINE" ]]; then
    CMD_BEFORE_DASH+=(-E "$RENDER_ENGINE")
fi

# 3. Output formats & GPU profile
CMD_BEFORE_DASH+=(
    -x 1
    -o "$WORK_DIR/$NAME"
    -F PNG
    --profile-gpu
)

# 4. User-provided extra Blender flags
if [[ -n "$BLENDER_EXTRA_ARGS" ]]; then
    # Word-split string into array
    read -r -a extra_blender <<< "$BLENDER_EXTRA_ARGS"
    CMD_BEFORE_DASH+=("${extra_blender[@]}")
fi

# 5. Pre-Render Setup Python Script (MUST precede render trigger -f / -a)
if [[ -n "$SETUP_SCRIPT" ]]; then
    if [[ ! -f "$SETUP_SCRIPT" ]]; then
        echo "ERROR: SETUP_SCRIPT specified but not found: $SETUP_SCRIPT" >&2
        exit 1
    fi
    CMD_BEFORE_DASH+=(-P "$SETUP_SCRIPT")
fi

# 6. Render Trigger (Animation or Single Frame)
if [[ "$RENDER_MODE" == "frame" ]]; then
    CMD_BEFORE_DASH+=(-f "$FRAME")
else
    CMD_BEFORE_DASH+=(-a)
fi

# 7. Flags after '--' (Consumable by Python sys.argv and Cycles CLI hook)
if [[ -n "$CYCLES_DEVICE" ]]; then
    CMD_AFTER_DASH+=(--cycles-device "$CYCLES_DEVICE")
fi

if [[ -n "$SETUP_ARGS" ]]; then
    read -r -a extra_setup <<< "$SETUP_ARGS"
    CMD_AFTER_DASH+=("${extra_setup[@]}")
fi

printf '%s\n' '========================================'
printf 'Render job\n'
printf '  name  : %s\n' "$NAME"
printf '  blend : %s\n' "$BLEND_FILE"
printf '  engine: %s\n' "${RENDER_ENGINE:-[from file/script]}"
if [[ -n "$SETUP_SCRIPT" ]]; then
    printf '  setup : %s\n' "$SETUP_SCRIPT"
    printf '  s-args: %s\n' "${SETUP_ARGS:-[none]}"
fi
printf '  work  : %s\n' "$WORK_DIR"
printf '  out   : %s\n' "$DEST"
printf '  log   : %s\n' "$BLENDER_LOG"
printf '%s\n' '========================================'

printf '%s\n' "$$" >"$JOB_PID_FILE"

BLENDER_PID=""
MOVER_PID=""

cleanup() {
    local status=${1:-143}
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

# ---------------------------------------------------------------------------
# Launch Blender Process
# ---------------------------------------------------------------------------
if [[ ${#CMD_AFTER_DASH[@]} -gt 0 ]]; then
    "${CMD_BEFORE_DASH[@]}" -- "${CMD_AFTER_DASH[@]}" >"$BLENDER_LOG" 2>&1 &
else
    "${CMD_BEFORE_DASH[@]}" >"$BLENDER_LOG" 2>&1 &
fi
BLENDER_PID=$!

# ---------------------------------------------------------------------------
# Start Mover Subprocess
# ---------------------------------------------------------------------------
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
