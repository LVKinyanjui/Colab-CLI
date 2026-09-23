#!/usr/bin/env bash

BLEND_FILE="$1"
DEST="$2"

NAME="$(basename "$BLEND_FILE" .blend)"
OUTDIR="$DEST/$NAME"

WORKDIR="/content/render_work"
LOGDIR="logs"

BLENDER_LOG="$LOGDIR/${NAME}.log"
MOVER_LOG="$LOGDIR/${NAME}-mover.log"

mkdir -p "$OUTDIR" "$WORKDIR" "$LOGDIR"

echo "========================================"
echo "Render job"
echo "  name : $NAME"
echo "  blend: $BLEND_FILE"
echo "  work : $WORKDIR"
echo "  out  : $OUTDIR"
echo "  log  : $BLENDER_LOG"
echo "========================================"

# Start Blender
blender \
    -b "$BLEND_FILE" \
    -E CYCLES \
    -x 1 \
    -o "$WORKDIR/$NAME" \
    -F PNG \
    --profile-gpu \
    -a \
    -- \
    --cycles-device CUDA+CPU \
    >"$BLENDER_LOG" 2>&1 &

BLENDER_PID=$!

# Start mover
(
    while kill -0 "$BLENDER_PID" 2>/dev/null; do

        printf '[%s] mover alive\n' \
            "$(date '+%F %T')"

        for f in "$WORKDIR"/"$NAME"*.png; do
            [ -f "$f" ] || continue

            size1=$(stat -c%s "$f" 2>/dev/null) || continue

            sleep 2

            size2=$(stat -c%s "$f" 2>/dev/null) || continue

            if [ "$size1" = "$size2" ]; then
                mv -- "$f" "$OUTDIR/"
                printf '[%s] moved %s (%s bytes)\n' \
                    "$(date '+%F %T')" \
                    "$(basename "$f")" \
                    "$size2"
            fi
        done

        sleep 10
    done

    printf '[%s] blender finished; final scan\n' \
        "$(date '+%F %T')"

    for f in "$WORKDIR"/"$NAME"*.png; do
        [ -f "$f" ] || continue

        size1=$(stat -c%s "$f" 2>/dev/null) || continue

        sleep 2

        size2=$(stat -c%s "$f" 2>/dev/null) || continue

        if [ "$size1" = "$size2" ]; then
            mv -- "$f" "$OUTDIR/"
            printf '[%s] final move %s (%s bytes)\n' \
                "$(date '+%F %T')" \
                "$(basename "$f")" \
                "$size2"
        fi
    done

) >"$MOVER_LOG" 2>&1 &

MOVER_PID=$!

# Wait for Blender
wait "$BLENDER_PID"
STATUS=$?

# Give mover a chance to perform its final scan
wait "$MOVER_PID"

echo
echo "Blender exited with status: $STATUS"

exit "$STATUS"
