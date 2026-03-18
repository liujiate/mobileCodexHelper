#!/usr/bin/env bash
set -euo pipefail

workspace="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
runtime_root="${MOBILE_CODEX_RUNTIME_DIR:-$workspace/.runtime}"

if [[ -n "${MOBILE_CODEX_NGINX:-}" ]]; then
  nginx_bin="$MOBILE_CODEX_NGINX"
else
  nginx_bin="$(command -v nginx || true)"
fi

if [[ -z "$nginx_bin" ]]; then
  for candidate in /opt/homebrew/bin/nginx /usr/local/bin/nginx; do
    if [[ -x "$candidate" ]]; then
      nginx_bin="$candidate"
      break
    fi
  done
fi

if [[ -z "${nginx_bin:-}" ]]; then
  echo "nginx not found on PATH. Set MOBILE_CODEX_NGINX if needed." >&2
  exit 1
fi

nginx_root="$runtime_root/nginx"
conf_root="$nginx_root/conf"
logs_root="$nginx_root/logs"
temp_root="$nginx_root/temp"

mkdir -p "$conf_root" "$logs_root" "$temp_root"
cp "$workspace/deploy/nginx-mobile-codex.conf" "$conf_root/mobile-codex-nginx.conf"
cp "$workspace/deploy/nginx-mime.types" "$conf_root/mime.types"

"$nginx_bin" -p "$nginx_root" -c conf/mobile-codex-nginx.conf
