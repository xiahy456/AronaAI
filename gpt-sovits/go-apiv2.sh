#!/usr/bin/env bash
# Start GPT-SoVITS API with watchdog (auto-restart on stall/crash)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

chmod +x "$SCRIPT_DIR/watch-apiv2.sh" 2>/dev/null || true
exec "$SCRIPT_DIR/watch-apiv2.sh" "$@"
