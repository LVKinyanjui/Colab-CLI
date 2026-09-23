#!/bin/bash

render_one() {
    blend="$1"
    name="${blend##*/}"
    name="${name%.blend}"

    job_dest="$DEST/$name"

    mkdir -p "$job_dest" logs

    blender \
        -b "$blend" \
        -E CYCLES \
        -x 1 \
        -o "//$name" \
        -F PNG \
        -a \
        -- \
        --cycles-device CUDA+CPU \
        --profile-gpu \
        >"logs/${name}.log" 2>&1 &

    bpid=$!

    (
        while kill -0 "$bpid" 2>/dev/null; do
            printf '[%s] mover alive; checking for %s*.png\n' \
                "$(date '+%F %T')" "$name"

            for f in "${name}"*.png; do
                [ -f "$f" ] || continue

                size1=$(stat -c%s "$f" 2>/dev/null) || continue
                sleep 2
                size2=$(stat -c%s "$f" 2>/dev/null) || continue

                if [ "$size1" = "$size2" ]; then
                    mv -- "$f" "$job_dest/"
                    printf '[%s] moved %s (%s bytes)\n' \
                        "$(date '+%F %T')" "$f" "$size2"
                fi
            done

            sleep 10
        done

        # Final pass
        for f in "${name}"*.png; do
            [ -f "$f" ] || continue

            size1=$(stat -c%s "$f" 2>/dev/null) || continue
            sleep 2
            size2=$(stat -c%s "$f" 2>/dev/null) || continue

            if [ "$size1" = "$size2" ]; then
                mv -- "$f" "$job_dest/"
                printf '[%s] final move: %s\n' \
                    "$(date '+%F %T')" "$f"
            fi
        done
    ) >"logs/${name}-mover.log" 2>&1 &

    mpid=$!

    wait "$bpid"
    wait "$mpid"
}
