#!/usr/bin/env bash
# Run exactly one model update at a time with host-local settings.
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
config_file="${ONTO_UPDATE_CONFIG:-${script_dir}/metadata/update.env}"
[[ -r $config_file ]] || { printf 'Missing private configuration: %s\n' "$config_file" >&2; exit 1; }
set -a
source "$config_file"
set +a

PROJECT_ROOT="${PROJECT_ROOT:?set PROJECT_ROOT in the private configuration}"
PUBLISH_HOST="${PUBLISH_HOST:?set PUBLISH_HOST in the private configuration}"
PUBLISH_COMMAND="${PUBLISH_COMMAND:?set PUBLISH_COMMAND in the private configuration}"

if [[ -n ${ONTO_BIN_DIR:-} ]]; then
    export PATH="${ONTO_BIN_DIR}:${PATH}"
fi
if [[ -n ${CUDA_BIN_DIR:-} ]]; then
    export PATH="${CUDA_BIN_DIR}:${PATH}"
fi
if [[ -n ${CUDA_LIB_DIR:-} ]]; then
    export LD_LIBRARY_PATH="${CUDA_LIB_DIR}:${LD_LIBRARY_PATH:-}"
fi

cd "$PROJECT_ROOT"
exec 9> metadata/update.lock
flock -n 9 || { printf 'Another DeepGOPlus update is running\n' >&2; exit 1; }

source venv/bin/activate
python update.py
