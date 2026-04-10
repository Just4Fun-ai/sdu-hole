#!/usr/bin/env bash
set -euo pipefail

# 山大树洞恢复脚本
# 用法:
#   sudo bash restore_sdu_hole.sh /opt/sdu-hole/backups/sduhole_20260410_033000.tar.gz

if [[ $# -lt 1 ]]; then
  echo "Usage: sudo bash restore_sdu_hole.sh <backup.tar.gz>"
  exit 1
fi

BACKUP_FILE="$1"
if [[ ! -f "${BACKUP_FILE}" ]]; then
  echo "[restore] 备份文件不存在: ${BACKUP_FILE}"
  exit 1
fi

DATA_DIR="${DATA_DIR:-/opt/sdu-hole/data}"
DB_FILE="${DB_FILE:-${DATA_DIR}/sdu_hole.db}"
UPLOAD_DIR="${UPLOAD_DIR:-${DATA_DIR}/uploads}"

echo "[restore] 即将从备份恢复:"
echo "  ${BACKUP_FILE}"
echo "[restore] 将覆盖:"
echo "  ${DB_FILE}"
echo "  ${UPLOAD_DIR}"
read -r -p "输入 YES 确认继续: " CONFIRM
if [[ "${CONFIRM}" != "YES" ]]; then
  echo "[restore] 已取消"
  exit 1
fi

mkdir -p "${DATA_DIR}"
TMP_DIR="$(mktemp -d)"
NOW="$(date +%Y%m%d_%H%M%S)"
ROLLBACK_DIR="${DATA_DIR}/rollback_${NOW}"
mkdir -p "${ROLLBACK_DIR}"

cleanup() {
  rm -rf "${TMP_DIR}" || true
}
trap cleanup EXIT

echo "[restore] 停止服务..."
systemctl stop sdu-hole || true

echo "[restore] 备份当前线上数据到 ${ROLLBACK_DIR} ..."
if [[ -f "${DB_FILE}" ]]; then
  cp -a "${DB_FILE}" "${ROLLBACK_DIR}/sdu_hole.db"
fi
if [[ -d "${UPLOAD_DIR}" ]]; then
  cp -a "${UPLOAD_DIR}" "${ROLLBACK_DIR}/uploads"
fi

echo "[restore] 解压备份..."
tar -xzf "${BACKUP_FILE}" -C "${TMP_DIR}"

if [[ ! -f "${TMP_DIR}/sdu_hole.db" ]]; then
  echo "[restore] 备份包中缺少 sdu_hole.db"
  systemctl start sdu-hole || true
  exit 1
fi

cp -a "${TMP_DIR}/sdu_hole.db" "${DB_FILE}"
if [[ -d "${TMP_DIR}/uploads" ]]; then
  rm -rf "${UPLOAD_DIR}"
  cp -a "${TMP_DIR}/uploads" "${UPLOAD_DIR}"
fi

echo "[restore] 启动服务..."
systemctl start sdu-hole
systemctl status sdu-hole --no-pager | sed -n '1,20p'

echo "[restore] 完成。若发现异常，可回滚目录:"
echo "  ${ROLLBACK_DIR}"
