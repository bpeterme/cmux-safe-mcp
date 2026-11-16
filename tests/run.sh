#!/usr/bin/env bash
# Runs the test suite. Needs python3 and git; no other dependencies.
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 -B -m unittest discover -s tests -v "$@"
