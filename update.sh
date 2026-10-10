#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Updating Zip to Text from ${ROOT}"
echo "This force-reinstalls the package so the running app matches this source."

exec "${ROOT}/install.sh" "$@"
