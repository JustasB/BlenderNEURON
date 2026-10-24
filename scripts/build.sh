#!/bin/bash
set -e

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
repo_dir="$(cd "$script_dir/.." && pwd -P)"
case "$(uname -m)" in
    x86_64|amd64) host_arch=amd64 ;;
    arm64|aarch64) host_arch=arm64 ;;
    *) echo "Unsupported host architecture: $(uname -m)" >&2; exit 1 ;;
esac
docker_platform="${DOCKER_PLATFORM:-linux/$host_arch}"

cd "$script_dir"

cleanup() {
    rm -rf blenderneuron
}
trap cleanup EXIT

cp -r "$repo_dir/blenderneuron" blenderneuron
docker build --platform "$docker_platform" -t blenderneuron:latest .
