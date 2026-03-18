#!/usr/bin/env bash
set -euo pipefail

workspace="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
upstream="${MOBILE_CODEX_UPSTREAM_DIR:-$workspace/vendor/claudecodeui-1.25.2}"
runtime_root="${MOBILE_CODEX_RUNTIME_DIR:-$workspace/.runtime}"

node_path="${MOBILE_CODEX_NODE:-$(command -v node || true)}"
nginx_path="${MOBILE_CODEX_NGINX:-$(command -v nginx || true)}"
if [[ -n "${MOBILE_CODEX_TAILSCALE:-}" ]]; then
  tailscale_path="$MOBILE_CODEX_TAILSCALE"
elif [[ -x "/Applications/Tailscale.app/Contents/MacOS/Tailscale" ]]; then
  tailscale_path="/Applications/Tailscale.app/Contents/MacOS/Tailscale"
else
  tailscale_path="$(command -v tailscale || true)"
fi
tmux_path="$(command -v tmux || true)"
python_path="$(command -v python3 || command -v python || true)"

cat <<EOF
Workspace       = $workspace
RuntimeRoot     = $runtime_root
UpstreamExists  = $( [[ -d "$upstream" ]] && echo True || echo False )
UpstreamPath    = $upstream
Node            = ${node_path:-}
Nginx           = ${nginx_path:-}
Tailscale       = ${tailscale_path:-}
Tmux            = ${tmux_path:-}
Python          = ${python_path:-}
EOF
