#!/usr/bin/env bash

URL="$1"
LIST="blend_urls.txt"

if ! command -v aria2c >/dev/null; then
    echo "aria2c not found — installing it..."
    sudo apt-get update -qq && sudo apt-get install -y aria2
fi

wget --spider -r -np "$URL" 2>&1 |
  grep -Eo 'https?://[^ ]+\.blend([?#][^ ]*)?' |
  sort -u > "$LIST"

aria2c -i "$LIST" -j 8 -c

