#!/usr/bin/env bash
set -euo pipefail

# 山大树洞自动备份脚本
# 默认备份：
# 1) SQLite 数据库（使用 sqlite3 backup 保证一致性）
# 2) 上传图片目录
# 输出：/opt/sdu-hole/backups/sduhole_YYYYmmdd_HHMMSS.tar.gz

DATA_DIR="${DATA_DIR:-/opt/sdu-hole/data}"
DB_FILE="${DB_FILE:-${DATA_DIR}/sdu_hole.db}"
UPLOAD_DIR="${UPLOAD_DIR:-${DATA_DIR}/uploads}"
BACKUP_ROOT="${BACKUP_ROOT:-/opt/sdu-hole/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

if [[ ! -f "${DB_FILE}" ]]; then
  echo "[backup] 数据库文件不存在: ${DB_FILE}"
  exit 1
fi

mkdir -p "${BACKUP_ROOT}"
TMP_DIR="$(mktemp -d)"
TS="$(date +%Y%m%d_%H%M%S)"
OUT_FILE="${BACKUP_ROOT}/sduhole_${TS}.tar.gz"

cleanup() {
  rm -rf "${TMP_DIR}" || true
}
trap cleanup EXIT

echo "[backup] 开始备份 ${TS}"
echo "[backup] DB=${DB_FILE}"
echo "[backup] UPLOAD_DIR=${UPLOAD_DIR}"

# 1) 备份数据库（在线一致性备份）
python3 - "${DB_FILE}" "${TMP_DIR}/sdu_hole.db" <<'PY'
import sqlite3, sys
src, dst = sys.argv[1], sys.argv[2]
src_conn = sqlite3.connect(src)
dst_conn = sqlite3.connect(dst)
with dst_conn:
    src_conn.backup(dst_conn)
src_conn.close()
dst_conn.close()
print("[backup] sqlite backup done")
PY

# 2) 备份上传目录（若存在）
if [[ -d "${UPLOAD_DIR}" ]]; then
  cp -a "${UPLOAD_DIR}" "${TMP_DIR}/uploads"
fi

# 3) 写入元信息
cat > "${TMP_DIR}/backup_meta.txt" <<EOF
timestamp=${TS}
db_file=${DB_FILE}
upload_dir=${UPLOAD_DIR}
host=$(hostname)
EOF

# 4) 打包
tar -czf "${OUT_FILE}" -C "${TMP_DIR}" .
sha256sum "${OUT_FILE}" > "${OUT_FILE}.sha256"

# 5) 清理旧备份
find "${BACKUP_ROOT}" -type f -name 'sduhole_*.tar.gz' -mtime +"${RETENTION_DAYS}" -delete
find "${BACKUP_ROOT}" -type f -name 'sduhole_*.tar.gz.sha256' -mtime +"${RETENTION_DAYS}" -delete

echo "[backup] 完成: ${OUT_FILE}"
