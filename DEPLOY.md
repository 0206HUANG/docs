# 部署指南（生产 / 客户演示）

整套系统用 Docker Compose 一键起：**Postgres(pgvector) + Redis + FastAPI + ARQ worker + Next.js 前端 + Caddy 反代**。Caddy 是唯一对外入口，负责 HTTPS 和转发。

---

## 1. 准备一台服务器

- Linux（Ubuntu 22.04+ 推荐），2 核 4G 起步
- 安装 Docker 与 Docker Compose：
  ```bash
  curl -fsSL https://get.docker.com | sh
  ```
- 开放安全组/防火墙的 **80、443** 端口

> **邮箱可达性**：本系统靠 IMAP/SMTP 直连邮箱。若要演示接 **Gmail**，服务器需能访问 Google（海外服务器直接可用；国内服务器建议改用国内企业邮箱 QQ/163/腾讯，或演示时用内置 Demo 数据）。

## 2. 拉取代码

```bash
git clone https://github.com/0206HUANG/docs.git emailai
cd emailai
```

## 3. 配置密钥

```bash
cp .env.example .env
```

编辑 `.env`，至少填这几项：

| 变量 | 怎么生成 / 填什么 |
|------|------------------|
| `POSTGRES_PASSWORD` | 自定义一个强密码 |
| `SECRET_KEY` | `openssl rand -hex 32` |
| `ENCRYPTION_KEY` | `python3 -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"` |
| `DOMAIN` | 有域名填 `mail.acme.com`（自动 HTTPS）；没有就留 `:80`（用 IP + HTTP 访问）|
| `PUBLIC_BASE_URL` | 有域名填 `https://mail.acme.com`；否则 `http://服务器IP` |

> 若用域名：先把域名 A 记录解析到服务器公网 IP，Caddy 会自动申请 Let's Encrypt 证书。

## 4. 启动

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

首次启动会自动建表（Alembic 迁移到 008）并灌入 Demo 数据。查看状态：

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f app
```

## 5. 访问

- 有域名：`https://你的域名`
- 无域名：`http://服务器公网IP`

**Demo 登录**（首次 seed 自动创建）：
- 企业域名：`demo.emailai.local`
- 邮箱：`admin@demo.emailai.local`
- 密码：`Admin@123456`

## 6. 上线前的配置（在网页里）

1. **设置 → AI 配置**：选提供商、填 API Key、点「测试连接」确认适配成功
2. **邮箱账号 → 绑定邮箱**：填真实企业邮箱的 IMAP/SMTP + 授权码，点「测试」
3. **知识库**：建分组、上传产品资料/话术
4. **设置 → 路由策略 / 黑白名单 / 敏感词**：按业务配置

---

## 运维

```bash
# 更新到最新代码
git pull && docker compose -f docker-compose.prod.yml up -d --build

# 备份数据库
docker compose -f docker-compose.prod.yml exec postgres pg_dump -U postgres emailai > backup.sql

# 查看某个服务日志
docker compose -f docker-compose.prod.yml logs -f worker

# 停止 / 重启
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml restart
```

数据持久化在 named volumes：`postgres_data`（数据库）、`app_storage`（附件/知识库文件）、`caddy_data`（证书）。`down` 不会删除它们；`down -v` 会。
