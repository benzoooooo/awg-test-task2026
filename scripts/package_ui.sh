#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/ui/dist"
DST="$ROOT/src/gitpulse/static"
rm -rf "$DST"
mkdir -p "$DST"
if [[ ! -d "$SRC" ]]; then
  echo "ui/dist missing; run ui build first" >&2
  exit 1
fi
cp -R "$SRC"/. "$DST"/
# ensure directory is not empty for packaging
touch "$DST/.gitkeep"
echo "packaged UI into $DST"
