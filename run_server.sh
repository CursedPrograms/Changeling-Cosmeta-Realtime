#!/usr/bin/env bash
# Your phone as the camera: a page on this PC (scan the QR code in the window); the PC paints the looks.
exec "$(dirname "$0")/run.sh" --phone "$@"
