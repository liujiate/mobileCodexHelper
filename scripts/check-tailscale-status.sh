#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${MOBILE_CODEX_TAILSCALE:-}" ]]; then
  tailscale_bin="$MOBILE_CODEX_TAILSCALE"
else
  tailscale_bin="$(command -v tailscale || true)"
fi

if [[ -z "$tailscale_bin" ]]; then
  echo "Tailscale CLI not found" >&2
  exit 1
fi

"$tailscale_bin" status --json
