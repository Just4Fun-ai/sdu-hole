# SDU Treehole Monorepo

项目已按常见习惯整理为前后端分层结构：

## 目录结构

- `frontend/`
  - `index.html`：前端主页面
  - `deploy-config.js`：线上 API 基地址注入文件
  - `user-agreement.html`：用户协议
  - `privacy-policy.html`：隐私政策
  - `dev/sdu-hole-frontend.jsx`：历史前端实验稿（开发参考）
- `sdu-hole/`
  - `app/`：FastAPI 后端代码
  - `.env.example`：环境变量模板
  - `requirements.txt`：后端依赖
- `deploy/cn-ip/`
  - 国内服务器部署脚本（含一键发布、备份、恢复、systemd、nginx）
- `DEPLOY_CN_IP.md`
  - 国内 IP 上线说明

## 运行与发布（当前）

- 本地开发后端：进入 `sdu-hole/` 启动 `uvicorn`
- 服务器发布：执行 `deploy/cn-ip/push_to_server.sh`
  - 脚本会把 `frontend/index.html` 同步到服务器 `/var/www/sdu-hole/index.html`
  - 自动保留线上 `.env` 与数据库，不覆盖生产数据

