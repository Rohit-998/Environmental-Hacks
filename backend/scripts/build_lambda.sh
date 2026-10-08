#!/usr/bin/env bash
# Builds the Lambda bundle without Docker, on any OS:
#   .build/app          our code (airday, handlers, rules, fixtures)
#   .build/deps/python  Linux x86_64 wheels for Python 3.12, from the locked requirements
# The SAM template points every function at .build/app and attaches .build/deps as a layer, so
# `sam deploy` uploads these folders directly. SAM's own pip builder can't be used on Windows hosts:
# it resolves platform markers for the host and pulls in pywin32.
set -euo pipefail
cd "$(dirname "$0")/.."

rm -rf .build
mkdir -p .build/app .build/deps/python

cp -r airday handlers rules .build/app/
mkdir -p .build/app/fixtures && cp -r fixtures/replay .build/app/fixtures/
find .build/app -name "__pycache__" -type d -prune -exec rm -rf {} +

uv pip install \
  --quiet \
  --requirement requirements.txt \
  --target .build/deps/python \
  --python-platform x86_64-manylinux2014 \
  --python-version 3.12 \
  --only-binary :all:
find .build/deps -name "__pycache__" -type d -prune -exec rm -rf {} +

echo "app:  $(du -sh .build/app | cut -f1)"
echo "deps: $(du -sh .build/deps | cut -f1) (Lambda layer limit: 250 MB unzipped)"
