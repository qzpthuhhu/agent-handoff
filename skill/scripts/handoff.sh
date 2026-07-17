#!/usr/bin/env bash
# Skill 用的便捷 shell wrapper,内部走 handoff.py
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/handoff.py" "$@"
