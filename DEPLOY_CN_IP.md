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
DATABASE_URL=sqlite+aiosqlite:///./sdu_hole.db
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
