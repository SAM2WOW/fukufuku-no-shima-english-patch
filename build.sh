#!/bin/sh
# Fukufuku no Shima English Translation - Linux/macOS build script
# Usage: ./build.sh [path/to/original.iso] [--xdelta]
cd "$(dirname "$0")" || exit 1
exec python3 tools/build.py "$@"
