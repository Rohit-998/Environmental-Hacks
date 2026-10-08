#!/usr/bin/env bash
# Writes requirements.txt for `sam build` from uv.lock, with the exact locked versions.
# Drops Windows-only packages (e.g. pywin32): Lambda runs on Linux, and SAM's resolver doesn't skip them by marker.
#
#   bash scripts/export_requirements.sh            # write requirements.txt
#   bash scripts/export_requirements.sh --check    # fail if requirements.txt is out of date (CI)
set -euo pipefail
cd "$(dirname "$0")/.."

out=$(uv export --frozen --no-dev --no-hashes --no-emit-project --extra agent --no-header --no-annotate \
  | grep -v "sys_platform == 'win32'")
body="# Generated from uv.lock by scripts/export_requirements.sh. Do not edit by hand.
$out"

if [[ "${1:-}" == "--check" ]]; then
  diff <(printf '%s\n' "$body") requirements.txt && echo "requirements.txt is up to date"
else
  printf '%s\n' "$body" > requirements.txt
  echo "wrote requirements.txt ($(grep -vc '^#' requirements.txt) packages)"
fi
