# 🕳️ 山大树洞 (SDU Hole)

山东大学匿名校园社区，基于 FastAPI + SQLite 构建。

## 快速开始（3步跑起来）

### 1. 创建环境并安装依赖

```bash
# 如果用 conda
conda create -n sduhole python=3.11 -y
conda activate sduhole

# 如果用 pyenv
pyenv install 3.11
pyenv local 3.11
python -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 创建配置文件

```bash
cp .env.example .env
# 默认使用控制台模式（验证码打印在终端），无需修改任何配置
```

### 3. 启动！

```bash
uvicorn app.main:app --reload --port 8000
```

看到以下输出就成功了：
```
🕳️  山大树洞 正在启动...
📧 邮件模式: console
🏫 邮箱后缀: @mail.sdu.edu.cn
✅ 数据库初始化完成
📖 API 文档: http://localhost:8000/docs
```

## 线上部署（可分享网址）

推荐组合：
- 后端 API：Railway（部署 `/Users/lesux/Code/sdutreehole/sdu-hole`）
- 前端网页：Vercel（部署 `/Users/lesux/Code/sdutreehole`）

### A. 部署后端到 Railway

1. 在 Railway 新建项目，选择从 GitHub 导入仓库（或本地上传）。
2. `Root Directory` 设为 `sdu-hole`。
3. 配置环境变量（至少这些）：

```env
SECRET_KEY=替换成随机长字符串
DATABASE_URL=postgresql://...                # Railway Postgres 提供的连接串也可直接贴
CORS_ORIGINS=https://你的前端域名.vercel.app
ALLOWED_EMAIL_SUFFIX=@mail.sdu.edu.cn

EMAIL_MODE=smtp
SMTP_HOST=smtp.163.com
SMTP_PORT=465
SMTP_USER=你的邮箱@163.com
SMTP_PASSWORD=你的SMTP授权码
SMTP_USE_STARTTLS=false
```

4. Railway 会自动执行 `uvicorn app.main:app --host 0.0.0.0 --port $PORT`（已在 `railway.toml` 配置）。
5. 部署成功后拿到后端地址，例如：`https://sdu-hole-api.up.railway.app`。

### B. 部署前端到 Vercel

1. 在 Vercel 导入同一个仓库。
2. 项目根目录使用仓库根目录（不是 `sdu-hole` 子目录）。
3. 由于根目录有 `vercel.json`，访问 `/` 会自动打开 `sdu-hole.html`。
4. 把根目录文件 `deploy-config.js` 改成你的后端地址：

```js
window.__SDU_API_BASE__ = "https://你的后端域名.up.railway.app";
```

5. 重新部署 Vercel，拿到前端地址，例如：`https://sdu-hole.vercel.app`。

### C. 联通检查

1. 打开前端地址，发送验证码。
2. 若报跨域错误，检查 Railway 的 `CORS_ORIGINS` 是否与前端域名完全一致。
3. 若报 SMTP 登录错误，检查 `SMTP_USER/SMTP_PASSWORD`（授权码）是否正确。
4. 若数据库连接错误，优先检查 `DATABASE_URL` 是否为有效 Postgres 地址。

## 国内服务器 IP 快速上线

如果你想先在国内云服务器用公网 IP 跑起来（不等备案先看效果），请看：

- [DEPLOY_CN_IP.md](/Users/lesux/Code/sdutreehole/DEPLOY_CN_IP.md)

## 测试登录流程

打开浏览器访问 **http://localhost:8000/docs** ，按以下步骤操作：

### Step 1: 发送验证码
点开 `POST /api/auth/send-code`，点 "Try it out"，输入：
```json
{
  "student_id": "202312345"
}
```
点 Execute。**去看终端**，验证码会打印在那里：
```
==================================================
  📧 验证码邮件（控制台模式）
  收件人: 202312345@mail.sdu.edu.cn
  验证码: 847293
  有效期: 5 分钟
==================================================
```

### Step 2: 验证登录
点开 `POST /api/auth/verify`，输入（code 填终端里看到的）：
```json
{
  "student_id": "202312345",
  "code": "847293"
}
```
成功后会返回 JWT Token：
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

### Step 3: 使用 Token 发帖
点击页面顶部的 🔒 **Authorize** 按钮，输入上一步拿到的 token。
然后就可以测试发帖、评论、点赞等接口了！

## 切换到真实邮件发送

当你准备好 SMTP 账号后，修改 `.env`：
```env
EMAIL_MODE=smtp
SMTP_HOST=smtp.163.com
SMTP_PORT=465
SMTP_USER=your-email@163.com
SMTP_PASSWORD=your-authorization-code
```

重启服务后，验证码就会真正发送到 `学号@mail.sdu.edu.cn` 邮箱了。

### SMTP 常见报错排查

- `SMTP 登录失败`：通常是 `SMTP_USER / SMTP_PASSWORD` 错误。
- `连接 SMTP 服务器超时`：通常是网络不可达（山大 SMTP 常见需要校园网）。
- `SMTP 连接被拒绝`：检查 `SMTP_HOST / SMTP_PORT` 是否正确，或服务器是否限制访问。
- `TLS 配置异常`：检查 `SMTP_PORT` 与 `SMTP_USE_STARTTLS` 是否匹配。

## 项目结构

```
sdu-hole/
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # 配置
│   ├── database.py          # 数据库
│   ├── models/              # 数据库模型
│   │   ├── user.py          # 用户（学号哈希存储）
│   │   ├── post.py          # 帖子
│   │   ├── comment.py       # 评论
│   │   └── like.py          # 点赞记录
│   ├── schemas/             # 请求/响应模型
│   ├── routers/             # API 路由
│   │   ├── auth.py          # 认证（发验证码+登录）
│   │   └── posts.py         # 帖子+评论+点赞
│   ├── services/            # 业务逻辑
│   │   ├── email.py         # 邮件发送（console/smtp双模式）
│   │   └── filter.py        # 敏感词过滤
│   └── utils/
│       ├── security.py      # JWT + 密码哈希
│       └── anonymous.py     # 匿名昵称生成
├── requirements.txt
├── .env.example
└── README.md
```

## API 接口一览

| 方法 | 路径 | 说明 | 需要登录 |
|------|------|------|----------|
| POST | `/api/auth/send-code` | 发送验证码 | ❌ |
| POST | `/api/auth/verify` | 验证码登录 | ❌ |
| GET | `/api/posts/` | 帖子列表 | ✅ |
| POST | `/api/posts/` | 发帖 | ✅ |
| GET | `/api/posts/{id}` | 帖子详情 | ✅ |
| POST | `/api/posts/{id}/like` | 点赞/取消 | ✅ |
| DELETE | `/api/posts/{id}` | 删除帖子 | ✅ |
| GET | `/api/posts/{id}/comments` | 评论列表 | ✅ |
| POST | `/api/posts/{id}/comments` | 发评论 | ✅ |
| GET | `/api/tags` | 标签列表 | ❌ |
