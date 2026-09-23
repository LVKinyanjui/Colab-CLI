#!/bin/bash

mkdir -p renders logs; blender -b loft.blend -E CYCLES -x 1 -o //loft -F PNG -a -- --cycles-device CUDA+CPU --profile-gpu >logs/blender.log 2>&1 & bpid=$!; (while kill -0 "$bpid" 2>/dev/null; do sleep 10; find . -maxdepth 1 -type f -name 'loft*.png' -exec mv -t renders/ -- {} +; done; find . -maxdepth 1 -type f -name 'loft*.png' -exec mv -t renders/ -- {} +) >logs/mover.log 2>&1 &

