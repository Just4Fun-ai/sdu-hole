#!/usr/bin/env bash
set -euo pipefail

# 在服务器上执行：
#   sudo bash /opt/sdu-hole/app/deploy/cn-ip/install_backup_timer.sh

APP_DIR="${APP_DIR:-/opt/sdu-hole/app}"

chmod +x "${APP_DIR}/deploy/cn-ip/backup_sdu_hole.sh"
chmod +x "${APP_DIR}/deploy/cn-ip/restore_sdu_hole.sh"

cp "${APP_DIR}/deploy/cn-ip/sdu-hole-backup.service" /etc/systemd/system/sdu-hole-backup.service
cp "${APP_DIR}/deploy/cn-ip/sdu-hole-backup.timer" /etc/systemd/system/sdu-hole-backup.timer

systemctl daemon-reload
systemctl enable --now sdu-hole-backup.timer

echo "==> 备份定时器状态"
systemctl status sdu-hole-backup.timer --no-pager | sed -n '1,20p'

echo "==> 手动试跑一次备份"
systemctl start sdu-hole-backup.service
sleep 1
journalctl -u sdu-hole-backup.service -n 20 --no-pager

echo "==> 最近备份文件"
ls -lh /opt/sdu-hole/backups | tail -n 10 || true
