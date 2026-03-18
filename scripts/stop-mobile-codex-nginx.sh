#!/usr/bin/env bash
set -euo pipefail

workspace="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
runtime_root="${MOBILE_CODEX_RUNTIME_DIR:-$workspace/.runtime}"
pid_file="$runtime_root/nginx/logs/mobile-codex.pid"

if [[ -f "$pid_file" ]]; then
  pid_value="$(head -n 1 "$pid_file" || true)"
  if [[ "$pid_value" =~ ^[0-9]+$ ]]; then
    kill "$pid_value" >/dev/null 2>&1 || true
  fi
fi

listeners="$(lsof -t -nP -iTCP:8080 -sTCP:LISTEN 2>/dev/null || true)"
if [[ -n "$listeners" ]]; then
  while IFS= read -r pid; do
    [[ -n "$pid" ]] || continue
    kill "$pid" >/dev/null 2>&1 || true
  done <<< "$listeners"
fi
