#!/usr/bin/env bash

URL="${1:-https://download.blender.org/demo/}"
LIST="blend_urls.txt"

if ! command -v aria2c >/dev/null; then
    echo "aria2c not found — installing it..."
    sudo apt-get update -qq >/dev/null 2>&1 &&
    sudo apt-get install -y aria2 >/dev/null 2>&1
fi

wget --spider -r -np "$URL" 2>&1 |
  grep -Eo 'https?://[^[:space:]]+/[^[:space:]]+\.blend([?#][^[:space:]]*)?' |
  sort -u > "$LIST"

aria2c -i "$LIST" -j 4 -c
