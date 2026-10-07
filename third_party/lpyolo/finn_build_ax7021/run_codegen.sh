#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
finn_root="$(cd "$script_dir/../../finn-0.7" && pwd)"

"$finn_root/run-docker.sh" build_custom "$script_dir"
