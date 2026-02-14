#!/usr/bin/env bash
# Thin wrapper around sag binary that maps SAG_API_KEY → ELEVENLABS_API_KEY
set -euo pipefail

# Map SAG_API_KEY to what the binary expects
if [ -n "${SAG_API_KEY:-}" ]; then
  export ELEVENLABS_API_KEY="${ELEVENLABS_API_KEY:-$SAG_API_KEY}"
elif [ -z "${ELEVENLABS_API_KEY:-}" ]; then
  echo "Error: Neither SAG_API_KEY nor ELEVENLABS_API_KEY is set." >&2
  echo "Set SAG_API_KEY in your environment (e.g. ~/.bashrc)." >&2
  exit 1
fi

exec /usr/local/bin/sag "$@"
