#!/usr/bin/env bash
# 在 Linux 上启动 API 服务（对应 go-apiv2.bat）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ ! -f api_v2.py ]]; then
  echo "Error: api_v2.py not found in $SCRIPT_DIR" >&2
  exit 1
fi

# Prefer bundled runtime (if present), otherwise system Python.
if [[ -x "$SCRIPT_DIR/runtime/bin/python" ]]; then
  PYTHON="$SCRIPT_DIR/runtime/bin/python"
elif [[ -x "$SCRIPT_DIR/runtime/python" ]]; then
  PYTHON="$SCRIPT_DIR/runtime/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  PYTHON="$(command -v python)"
else
  echo "Error: Python not found. Install Python 3 or place a runtime under ./runtime/" >&2
  exit 1
fi

exec "$PYTHON" -I api_v2.py
