#!/usr/bin/env bash
# Atualiza o jev-o-matic-prd pro commit da main e roda o smoke. O CD só cobre o -test;
# produção é sempre um ato deliberado, do Mac.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTAINER_NAME=jev-o-matic-prd APP_URL=https://jev-o-matic.oute.pro "${DIR}/deploy-test.sh"
"${DIR}/smoke.sh" prd
