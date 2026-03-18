#!/usr/bin/env bash
set -euo pipefail

workspace="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_root="$workspace/upstream-overrides/claudecodeui-1.25.2"
target_root="${MOBILE_CODEX_UPSTREAM_DIR:-$workspace/vendor/claudecodeui-1.25.2}"

if [[ ! -d "$source_root" ]]; then
  echo "Override source not found: $source_root" >&2
  exit 1
fi

if [[ ! -d "$target_root" ]]; then
  echo "Upstream checkout not found: $target_root" >&2
  exit 1
fi

copied=0
while IFS= read -r -d '' file_path; do
  relative_path="${file_path#$source_root/}"
  destination="$target_root/$relative_path"
  mkdir -p "$(dirname "$destination")"
  cp "$file_path" "$destination"
  copied=$((copied + 1))
done < <(find "$source_root" -type f -print0)

echo "Applied $copied override files to $target_root"
