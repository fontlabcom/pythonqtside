#!/bin/sh
# this_file: test.sh
set -eu
uv run --no-sync python -m pytest "$@"
