#!/usr/bin/env bash
# Publish one new sourced page from the queue, then rebuild the static site.
# Intended for a scheduled routine. It will not invent data, send email,
# deploy, or sign up for anything.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if ! command -v python3 >/dev/null 2>&1; then
  echo "nightly.sh needs python3 on PATH" >&2
  exit 1
fi

python3 "$ROOT/build.py" --status
python3 "$ROOT/build.py" --nightly
