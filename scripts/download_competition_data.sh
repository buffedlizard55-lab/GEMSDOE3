#!/usr/bin/env bash
# Hash-pinned bridge restoration. Prefer an explicitly chosen/activated interpreter,
# then this project's environment, without relying on shell state from an earlier call.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -n "${PYTHON:-}" ]]; then
  interpreter="$PYTHON"
elif [[ -n "${VIRTUAL_ENV:-}${CONDA_PREFIX:-}" ]]; then
  interpreter=python
elif [[ -x .venv/bin/python ]]; then
  interpreter=.venv/bin/python
else
  interpreter=python3
fi
"$interpreter" -m gems3.data download
