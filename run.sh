#!/usr/bin/env bash
# Changeling Cosmetics Realtime runs in Changeling CopyCat Realtime's environment with Changeling Cosmetics' code:
# both next to this folder (as in Changeling Studio). Missing ones are fetched here.
set -e
cd "$(dirname "$0")"
STUDIO="$(cd .. && pwd)"
for a in Cosmetics CopyCat-Realtime; do
    if [ ! -d "$STUDIO/Changeling-$a" ]; then
        echo "Getting Changeling $a ..."
        git clone "https://github.com/CursedPrograms/Changeling-$a" "$STUDIO/Changeling-$a"
    fi
done
PY="$STUDIO/Changeling-CopyCat-Realtime/venv/bin/python"
[ -x "$STUDIO/Changeling-CopyCat-Realtime/venv/Scripts/python.exe" ] && PY="$STUDIO/Changeling-CopyCat-Realtime/venv/Scripts/python.exe"
if [ ! -x "$PY" ]; then
    echo "Setting up Changeling CopyCat Realtime first, once: its environment and its models. Close its window when it opens."
    bash "$STUDIO/Changeling-CopyCat-Realtime/run.sh" --no-virtual
fi
exec "$PY" cosmetics_live.py "$@"
