#!/usr/bin/env bash

BLEND_FILE="$1"
DEST="$2"

NAME="$(basename "$BLEND_FILE" .blend)"
OUTDIR="$DEST/$NAME"
LOG="logs/${NAME}.log"

mkdir -p "$OUTDIR" logs

echo "========================================"
echo "Render job"
echo "  name : $NAME"
echo "  blend: $BLEND_FILE"
echo "  out  : $OUTDIR"
echo "  log  : $LOG"
echo "========================================"

blender \
    -b "$BLEND_FILE" \
    -E CYCLES \
    -x 1 \
    -o "$OUTDIR/$NAME" \
    -F PNG \
    --profile-gpu \
    -a \
    -- \
    --cycles-device CUDA+CPU \
    >"$LOG" 2>&1

STATUS=$?

echo
echo "Blender exited with status: $STATUS"
exit "$STATUS"
