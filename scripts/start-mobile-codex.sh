#!/usr/bin/env bash
set -euo pipefail

workspace="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
repo="${MOBILE_CODEX_UPSTREAM_DIR:-$workspace/vendor/claudecodeui-1.25.2}"
runtime_root="${MOBILE_CODEX_RUNTIME_DIR:-$workspace/.runtime}"
session_file="$runtime_root/mobile-codex-app.tmux-session"

if [[ ! -d "$repo" ]]; then
  echo "Upstream checkout not found: $repo" >&2
  exit 1
fi

if [[ -n "${MOBILE_CODEX_NODE:-}" ]]; then
  node_bin="$MOBILE_CODEX_NODE"
else
  node_bin="$(command -v node || true)"
fi

if [[ -z "$node_bin" ]]; then
  echo "Node.js 22 LTS not found on PATH. Set MOBILE_CODEX_NODE if needed." >&2
  exit 1
fi

tmux_bin="$(command -v tmux || true)"
if [[ -z "$tmux_bin" ]]; then
  echo "tmux not found on PATH. Install tmux for macOS background startup." >&2
  exit 1
fi

if [[ ! -f "$repo/dist/index.html" ]]; then
  npm_bin="$(command -v npm || true)"
  if [[ -z "$npm_bin" ]]; then
    echo "Frontend build is missing and npm was not found on PATH." >&2
    exit 1
  fi
  (
    cd "$repo"
    "$npm_bin" run build
  )
fi

log_dir="$workspace/tmp/logs"
stdout_log="$log_dir/mobile-codex-app.stdout.log"
stderr_log="$log_dir/mobile-codex-app.stderr.log"

mkdir -p "$runtime_root" "$log_dir"
printf '\n==== START %s ====\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" >> "$stdout_log"
printf '\n==== START %s ====\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" >> "$stderr_log"

export NODE_ENV=production
export HOST=127.0.0.1
export PORT=3001
export CODEX_ONLY_HARDENED_MODE=true
export VITE_CODEX_ONLY_HARDENED_MODE=true

session_hash="$(printf '%s' "$workspace" | shasum | awk '{print substr($1,1,8)}')"
session_name="mobile-codex-$session_hash"

"$tmux_bin" kill-session -t "$session_name" 2>/dev/null || true

printf -v escaped_repo '%q' "$repo"
printf -v escaped_node '%q' "$node_bin"
printf -v escaped_stdout '%q' "$stdout_log"
printf -v escaped_stderr '%q' "$stderr_log"
command_string="cd $escaped_repo && exec env NODE_ENV=production HOST=127.0.0.1 PORT=3001 CODEX_ONLY_HARDENED_MODE=true VITE_CODEX_ONLY_HARDENED_MODE=true $escaped_node server/index.js >> $escaped_stdout 2>> $escaped_stderr"

"$tmux_bin" new-session -d -s "$session_name" "$command_string"
echo "$session_name" > "$session_file"
