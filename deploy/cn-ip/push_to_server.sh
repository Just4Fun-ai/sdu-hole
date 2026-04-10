#!/usr/bin/env bash
set -euo pipefail

# One-command deploy from local Mac/Linux -> Tencent Cloud server
# Usage:
#   bash deploy/cn-ip/push_to_server.sh 82.157.101.92
# Optional env:
#   SERVER_USER=ubuntu APP_DIR=/opt/sdu-hole/app SKIP_PIP=1

if [[ $# -lt 1 ]]; then
  echo "Usage: bash deploy/cn-ip/push_to_server.sh <server_ip>"
  exit 1
fi

SERVER_IP="$1"
SERVER_USER="${SERVER_USER:-ubuntu}"
APP_DIR="${APP_DIR:-/opt/sdu-hole/app}"
ARCHIVE_LOCAL="/tmp/sdu-hole.tar.gz"
ARCHIVE_REMOTE="~/sdu-hole.tar.gz"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "==> Packing project from: ${ROOT_DIR}"
tar \
  --exclude=".git" \
  --exclude=".DS_Store" \
  --exclude="._*" \
  --exclude="__MACOSX" \
  --exclude="sdu-hole/.env" \
  --exclude="sdu-hole/sdu_hole.db" \
  --exclude="**/__pycache__" \
  --exclude="**/*.pyc" \
  -czf "${ARCHIVE_LOCAL}" \
  -C "${ROOT_DIR}" .

echo "==> Uploading archive to ${SERVER_USER}@${SERVER_IP}"
scp "${ARCHIVE_LOCAL}" "${SERVER_USER}@${SERVER_IP}:${ARCHIVE_REMOTE}"

echo "==> Deploying on server (may ask sudo password)"
ssh -t "${SERVER_USER}@${SERVER_IP}" "
set -euo pipefail
ENV_BAK='/tmp/sdu-hole.env.bak'
if [ -f '${APP_DIR}/sdu-hole/.env' ]; then
  sudo cp '${APP_DIR}/sdu-hole/.env' \"\$ENV_BAK\"
fi

sudo mkdir -p '${APP_DIR}'
sudo rm -rf '${APP_DIR}'/*
sudo tar -xzf ~/sdu-hole.tar.gz -C '${APP_DIR}'

if [ -f \"\$ENV_BAK\" ]; then
  sudo mkdir -p '${APP_DIR}/sdu-hole'
  sudo mv \"\$ENV_BAK\" '${APP_DIR}/sdu-hole/.env'
fi

if [ \"\${SKIP_PIP:-0}\" != \"1\" ]; then
  sudo /opt/sdu-hole/venv/bin/pip install -r '${APP_DIR}/sdu-hole/requirements.txt'
fi

sudo systemctl restart sdu-hole
sudo systemctl restart nginx
sudo systemctl --no-pager --full status sdu-hole | sed -n '1,20p'
"

echo
echo "==> Deploy complete"
echo "Open: http://${SERVER_IP}"
