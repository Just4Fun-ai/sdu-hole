# 山大树洞：国内服务器 IP 快速上线（最快可当天看到结果）

适用目标：
- 先用国内服务器公网 IP 上线验证
- 后续再切域名 + 备案 + HTTPS

## 1. 服务器准备

推荐配置（最低可用）：
- Ubuntu 22.04
- 2C2G
- 安全组开放：`22, 80, 443`

## 2. 登录服务器并安装依赖

```bash
ssh root@你的服务器IP

apt update
apt install -y git python3 python3-venv nginx
```

## 3. 拉取项目并创建运行目录

```bash
mkdir -p /opt/sdu-hole
cd /opt/sdu-hole
git clone https://github.com/Just4Fun-ai/sdu-hole.git app

python3 -m venv /opt/sdu-hole/venv
/opt/sdu-hole/venv/bin/pip install -U pip
/opt/sdu-hole/venv/bin/pip install -r /opt/sdu-hole/app/sdu-hole/requirements.txt
```

## 4. 配置后端环境变量

```bash
cp /opt/sdu-hole/app/sdu-hole/.env.example /opt/sdu-hole/app/sdu-hole/.env
nano /opt/sdu-hole/app/sdu-hole/.env
```

至少改这些：

```env
SECRET_KEY=换成随机长字符串
DATABASE_URL=sqlite+aiosqlite:////opt/sdu-hole/data/sdu_hole.db
IMAGE_UPLOAD_DIR=/opt/sdu-hole/data/uploads
CORS_ORIGINS=*
ALLOWED_EMAIL_SUFFIX=@mail.sdu.edu.cn

EMAIL_MODE=smtp
SMTP_HOST=smtp.163.com
SMTP_PORT=465
SMTP_USER=你的163邮箱@163.com
SMTP_PASSWORD=你的SMTP授权码
SMTP_USE_STARTTLS=false
```

## 5. 配置 systemd 启动后端

```bash
cp /opt/sdu-hole/app/deploy/cn-ip/sdu-hole.service /etc/systemd/system/sdu-hole.service

systemctl daemon-reload
systemctl enable sdu-hole
systemctl restart sdu-hole
systemctl status sdu-hole --no-pager
```

如果启动失败，看日志：

```bash
journalctl -u sdu-hole -n 100 --no-pager
```

## 6. 配置 Nginx（同一 IP 提供前端 + 反向代理后端）

```bash
cp /opt/sdu-hole/app/deploy/cn-ip/nginx-sdu-hole.conf /etc/nginx/sites-available/sdu-hole.conf
ln -sf /etc/nginx/sites-available/sdu-hole.conf /etc/nginx/sites-enabled/sdu-hole.conf
rm -f /etc/nginx/sites-enabled/default

nginx -t
systemctl restart nginx
```

## 7. 验证上线

浏览器访问：

```txt
http://你的服务器IP
```

API 文档：

```txt
http://你的服务器IP/docs
```

## 8. 代码更新（以后每次发布）

推荐使用本仓库的一键安全发布脚本（不会覆盖线上数据库）：

```bash
# 本地终端执行
cd 你的项目目录
bash deploy/cn-ip/push_to_server.sh 你的服务器IP
```

如果你手动在服务器 `git pull`，请务必确保：
- `.env` 没被覆盖
- `DATABASE_URL` 仍是 `/opt/sdu-hole/data/sdu_hole.db`

可用下面命令快速核对：

```bash
# 服务器终端执行
cd /opt/sdu-hole/app/sdu-hole
grep '^DATABASE_URL=' .env
```

仅在需要手工更新时再用：

```bash
cd /opt/sdu-hole/app
git pull
/opt/sdu-hole/venv/bin/pip install -r /opt/sdu-hole/app/sdu-hole/requirements.txt
systemctl restart sdu-hole
systemctl restart nginx
```

## 9. 后续正式化（建议）

1. 购买域名并完成 ICP 备案
2. 域名解析到服务器 IP
3. 用 Nginx + Let's Encrypt 配 HTTPS
4. 把 `CORS_ORIGINS` 从 `*` 改成你的正式域名

## 10. 自动备份（强烈建议）

在服务器终端执行（SSH 后）：

```bash
sudo bash /opt/sdu-hole/app/deploy/cn-ip/install_backup_timer.sh
```

默认行为：
- 每天 `03:30` 自动备份一次
- 备份内容：数据库 + 上传图片目录
- 备份目录：`/opt/sdu-hole/backups`
- 默认保留 14 天（可在 `backup_sdu_hole.sh` 里改 `RETENTION_DAYS`）

手动备份：

```bash
sudo bash /opt/sdu-hole/app/deploy/cn-ip/backup_sdu_hole.sh
```

恢复：

```bash
sudo bash /opt/sdu-hole/app/deploy/cn-ip/restore_sdu_hole.sh /opt/sdu-hole/backups/你的备份包.tar.gz
```
