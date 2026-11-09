#!/usr/bin/env bash
# Changeling Cosmeta Realtime runs in Changeling Imago Realtime's environment with Changeling Cosmeta' code:
# both next to this folder (as in Changeling Studio). Missing ones are fetched here.
set -e
cd "$(dirname "$0")"
STUDIO="$(cd .. && pwd)"
for a in Cosmeta Imago-Realtime; do
    if [ ! -d "$STUDIO/Changeling-$a" ]; then
        echo "Getting Changeling $a ..."
        git clone "https://github.com/CursedPrograms/Changeling-$a" "$STUDIO/Changeling-$a"
    fi
done
PY="$STUDIO/Changeling-Imago-Realtime/venv/bin/python"
[ -x "$STUDIO/Changeling-Imago-Realtime/venv/Scripts/python.exe" ] && PY="$STUDIO/Changeling-Imago-Realtime/venv/Scripts/python.exe"
if [ ! -x "$PY" ]; then
    echo "Setting up Changeling Imago Realtime first, once: its environment and its models. Close its window when it opens."
    bash "$STUDIO/Changeling-Imago-Realtime/run.sh" --no-virtual
fi
exec "$PY" cosmetics_live.py "$@"
