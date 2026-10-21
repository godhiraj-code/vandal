#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# No inherited credentials, proxy variables, Python hooks or pip configuration.
exec env -i PATH="$PATH" PIP_CONFIG_FILE=/dev/null PYTHONUTF8=1 \
  python3 -I "$script_dir/fetch.py" "$@"
