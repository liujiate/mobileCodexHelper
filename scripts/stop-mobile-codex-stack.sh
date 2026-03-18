#!/usr/bin/env bash
set -euo pipefail

workspace="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
runtime_root="${MOBILE_CODEX_RUNTIME_DIR:-$workspace/.runtime}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
session_file="$runtime_root/mobile-codex-app.tmux-session"

"/bin/bash" "$script_dir/stop-mobile-codex-nginx.sh"

tmux_bin="$(command -v tmux || true)"
if [[ -n "$tmux_bin" && -f "$session_file" ]]; then
  session_name="$(head -n 1 "$session_file" || true)"
  if [[ -n "$session_name" ]]; then
    "$tmux_bin" kill-session -t "$session_name" >/dev/null 2>&1 || true
  fi
fi

app_pid_file="$runtime_root/mobile-codex-app.pid"
if [[ -f "$app_pid_file" ]]; then
  pid_value="$(head -n 1 "$app_pid_file" || true)"
  if [[ "$pid_value" =~ ^[0-9]+$ ]]; then
    kill "$pid_value" >/dev/null 2>&1 || true
  fi
fi

for port in 3001 8080; do
  listeners="$(lsof -t -nP -iTCP:${port} -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -z "$listeners" ]]; then
    continue
  fi
  while IFS= read -r pid; do
    [[ -n "$pid" ]] || continue
    kill "$pid" >/dev/null 2>&1 || true
  done <<< "$listeners"
done

rm -f "$app_pid_file" "$session_file"
