#!/usr/bin/env bash
set -euo pipefail

workspace="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$workspace"

python3 -m pip install -r requirements.txt
pyinstaller --noconfirm --clean MobileCodexControl.spec
