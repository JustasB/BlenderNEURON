#!/bin/bash
# Run from any directory. Remaining arguments configure the render.
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
output_dir="${OUTPUT_DIR:-$repo_dir/tutorials/02-docker-script/output}"
mkdir -p "$output_dir"
output_dir="$(cd "$output_dir" && pwd -P)"
"$repo_dir/scripts/build.sh"
docker run --rm --init \
  -v "$repo_dir:/BlenderNEURON:ro" \
  -v "$output_dir:/output" -w /BlenderNEURON \
  blenderneuron:latest python -u tutorials/02-docker-script/run.py "$@"
