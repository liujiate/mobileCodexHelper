#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"/bin/bash" "$script_dir/start-mobile-codex.sh"
sleep 5
"/bin/bash" "$script_dir/start-mobile-codex-nginx.sh"
