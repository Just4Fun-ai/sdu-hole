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
TMP_EXTRACT='/tmp/sdu-hole-deploy'
DATA_DIR='/opt/sdu-hole/data'
DB_FILE=\"\${DATA_DIR}/sdu_hole.db\"
if [ -f '${APP_DIR}/sdu-hole/.env' ]; then
  sudo cp '${APP_DIR}/sdu-hole/.env' \"\$ENV_BAK\"
fi

sudo mkdir -p '${APP_DIR}'
sudo rm -rf \"\${TMP_EXTRACT}\"
sudo mkdir -p \"\${TMP_EXTRACT}\"
sudo tar -xzf ~/sdu-hole.tar.gz -C \"\${TMP_EXTRACT}\"
sudo mkdir -p '${APP_DIR}'
sudo rsync -a --delete \"\${TMP_EXTRACT}/\" '${APP_DIR}/'
sudo rm -rf \"\${TMP_EXTRACT}\"

if [ -f \"\$ENV_BAK\" ]; then
  sudo mkdir -p '${APP_DIR}/sdu-hole'
  sudo mv \"\$ENV_BAK\" '${APP_DIR}/sdu-hole/.env'
fi

sudo mkdir -p \"\${DATA_DIR}\"
# 首次迁移：如果旧路径有数据库，则迁移到固定数据目录
if [ ! -f \"\${DB_FILE}\" ] && [ -f '${APP_DIR}/sdu-hole/sdu_hole.db' ]; then
  sudo cp -a '${APP_DIR}/sdu-hole/sdu_hole.db' \"\${DB_FILE}\"
fi

# 强制固定数据库路径，避免部署后回退到相对路径数据库
if sudo grep -q '^DATABASE_URL=' '${APP_DIR}/sdu-hole/.env' 2>/dev/null; then
  sudo sed -i 's#^DATABASE_URL=.*#DATABASE_URL=sqlite+aiosqlite:////opt/sdu-hole/data/sdu_hole.db#' '${APP_DIR}/sdu-hole/.env'
else
  echo 'DATABASE_URL=sqlite+aiosqlite:////opt/sdu-hole/data/sdu_hole.db' | sudo tee -a '${APP_DIR}/sdu-hole/.env' >/dev/null
fi
if sudo grep -q '^IMAGE_UPLOAD_DIR=' '${APP_DIR}/sdu-hole/.env' 2>/dev/null; then
  sudo sed -i 's#^IMAGE_UPLOAD_DIR=.*#IMAGE_UPLOAD_DIR=/opt/sdu-hole/data/uploads#' '${APP_DIR}/sdu-hole/.env'
else
  echo 'IMAGE_UPLOAD_DIR=/opt/sdu-hole/data/uploads' | sudo tee -a '${APP_DIR}/sdu-hole/.env' >/dev/null
fi
sudo mkdir -p /opt/sdu-hole/data/uploads

if [ \"\${SKIP_PIP:-0}\" != \"1\" ]; then
  sudo /opt/sdu-hole/venv/bin/pip install -r '${APP_DIR}/sdu-hole/requirements.txt'
fi

# Sync frontend static files for Nginx
sudo mkdir -p /var/www/sdu-hole
if [ -f '${APP_DIR}/sdu-hole.html' ]; then
  sudo cp '${APP_DIR}/sdu-hole.html' /var/www/sdu-hole/index.html
fi
if [ -f '${APP_DIR}/deploy-config.js' ]; then
  sudo cp '${APP_DIR}/deploy-config.js' /var/www/sdu-hole/deploy-config.js
fi
if [ -f '${APP_DIR}/user-agreement.html' ]; then
  sudo cp '${APP_DIR}/user-agreement.html' /var/www/sdu-hole/user-agreement.html
fi
if [ -f '${APP_DIR}/privacy-policy.html' ]; then
  sudo cp '${APP_DIR}/privacy-policy.html' /var/www/sdu-hole/privacy-policy.html
fi

sudo systemctl restart sdu-hole
sudo systemctl restart nginx
sudo systemctl --no-pager --full status sdu-hole | sed -n '1,20p'
echo '==> Effective DATABASE_URL in server env:'
sudo grep '^DATABASE_URL=' '${APP_DIR}/sdu-hole/.env' || true
echo '==> Existing DB file:'
sudo ls -lh /opt/sdu-hole/data/sdu_hole.db || true
"

echo
echo "==> Deploy complete"
echo "Open: http://${SERVER_IP}"
