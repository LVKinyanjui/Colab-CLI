#!/usr/bin/env bash
set -u

# Stop the active render scheduler and all render jobs it launched.
# This deliberately kills the scheduler first/last as part of the same
# shutdown operation so it cannot replenish Blender processes after they die.

STATE_DIR=${JOB_STATE_DIR:-$PWD/.render_state}
SCHEDULER_PID_FILE="$STATE_DIR/scheduler.pid"

if [[ ! -f "$SCHEDULER_PID_FILE" ]]; then
    echo "No active render scheduler found (missing $SCHEDULER_PID_FILE)."
    exit 0
fi

SCHEDULER_PID=$(cat "$SCHEDULER_PID_FILE" 2>/dev/null || true)

if [[ ! "$SCHEDULER_PID" =~ ^[0-9]+$ ]]; then
    echo "Invalid scheduler PID file: $SCHEDULER_PID_FILE" >&2
    exit 1
fi

if ! kill -0 "$SCHEDULER_PID" 2>/dev/null; then
    echo "Scheduler PID $SCHEDULER_PID is no longer running. Cleaning stale state."
    rm -f -- "$SCHEDULER_PID_FILE"
    exit 0
fi

echo "Stopping render scheduler PID $SCHEDULER_PID and its active jobs..."

# Ask the scheduler to shut down. Its trap propagates TERM to active
# render_job.sh wrappers, and each wrapper terminates Blender + its mover.
kill -TERM "$SCHEDULER_PID" 2>/dev/null || true

# Give the shutdown chain a moment to propagate.
sleep 2

# Safety net: find direct descendants of the scheduler that may still exist.
# Descendants are collected before force-killing so the scheduler cannot spawn
# replacements while we clean up.
collect_descendants() {
    local parent=$1
    local child
    for child in $(pgrep -P "$parent" 2>/dev/null || true); do
        echo "$child"
        collect_descendants "$child"
    done
}

DESCENDANTS=$(collect_descendants "$SCHEDULER_PID" || true)

for pid in $DESCENDANTS; do
    kill -TERM "$pid" 2>/dev/null || true
done

# If anything from the scheduler tree survives, force it down.
sleep 1

for pid in $DESCENDANTS "$SCHEDULER_PID"; do
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
        echo "Force stopping PID $pid"
        kill -KILL "$pid" 2>/dev/null || true
    fi
done

rm -f -- "$SCHEDULER_PID_FILE"

# Clean up stale job PID markers left by an interrupted shutdown.
find "$STATE_DIR" -maxdepth 1 -type f -name 'job-*.pid' -delete 2>/dev/null || true

echo "Render scheduler and its jobs stopped."
