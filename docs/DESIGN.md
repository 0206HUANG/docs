# 企业邮箱 AI 托管系统 — 架构设计文档

## 1. 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                          Internet                               │
│         企业邮件服务器 (腾讯企业邮/网易/Outlook/标准IMAP)           │
└──────────────────────────┬──────────────────────────────────────┘
                           │ IMAP IDLE / 轮询
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Application                         │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────┐    │
│  │  REST API   │  │  WebSocket   │  │   ARQ Worker        │    │
│  │  /api/v1/   │  │  /ws/notify  │  │  (邮件轮询/处理/总结) │    │
│  └──────┬──────┘  └──────┬───────┘  └──────────┬──────────┘    │
│         │                │                     │               │
│  ┌──────▼──────────────────────────────────────▼──────────┐    │
│  │                   Core Pipeline                         │    │
│  │  InboxPoller → Dedup → Thread → Classify → RAG →       │    │
│  │  ReplyGen → RouteDecision → Send/Draft/HumanQueue       │    │
│  └──────────────────────────────────────────────────────┘    │
│                           │                                    │
│         ┌─────────────────┼──────────────────┐                │
│         ▼                 ▼                  ▼                │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐        │
│  │  PostgreSQL │  │    Redis     │  │  File Storage  │        │
│  │  + pgvector │  │  (Queue/Cache│  │  (附件/知识库   │        │
│  └─────────────┘  └──────────────┘  └───────────────┘        │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│               Next.js 14 Admin Frontend                         │
│  收件箱 / 工单 / 知识库 / 账号管理 / 报表 / 系统设置              │
└─────────────────────────────────────────────────────────────────┘
```

### 核心处理流水线

```
收件 (IMAP IDLE)
    │
    ▼
去重检查 (Message-ID → emails 表)
    │ 新邮件
    ▼
线程聚合 (In-Reply-To / References → email_threads)
    │
    ▼
敏感词阻断检查 (优先级最高，命中即 → 人工队列 + 告警)
    │ 未命中
    ▼
LLM 分类 (类型/语言/紧急度/敏感词二次确认)
    │
    ├──→ 垃圾/广告/钓鱼 → 标记隔离，不回复
    │
    ▼
RAG 检索 (pgvector 按邮箱定位+邮件类型选知识库分组)
    │
    ├──→ 检索无结果 → 降级转人工
    │
    ▼
LLM 回复生成 (用来信语言 / 租户配置语气 / 禁止编造)
    │
    ▼
路由决策 (按邮件类型 × 租户策略配置)
    ├──→ AUTO_SEND  → 发送 + 归档
    ├──→ DRAFT_REVIEW → 生成草稿，创建审核工单
    └──→ HUMAN_ONLY → 直接创建人工工单，通知管理员

全程写入 audit_logs (每个步骤独立一条)
```

### 多租户隔离

- 所有业务表含 `tenant_id` 列，仓储层 `BaseTenantRepo` 自动注入过滤
- FastAPI Dependency 从 JWT 提取 `tenant_id`，传入所有服务
- 行级别：ORM 查询模型继承 `TenantMixin`，`get_all / get_by_id` 强制 `WHERE tenant_id = :tid`
- 跨租户 / 跨部门 403 由 `PermissionGuard` 装饰器强制

---

## 2. 数据库 ER 设计

### 租户 & 用户

```
tenants
  id            UUID PK
  name          VARCHAR(100)
  domain        VARCHAR(100) UNIQUE
  plan          VARCHAR(20)   -- free/pro/enterprise
  is_active     BOOLEAN
  settings      JSONB         -- LLM provider/model/api_key_enc, 语气, 定时总结配置
  created_at    TIMESTAMPTZ

users
  id            UUID PK
  tenant_id     UUID FK→tenants   -- 索引
  email         VARCHAR(200)
  name          VARCHAR(100)
  hashed_pw     VARCHAR(200)
  is_active     BOOLEAN
  created_at    TIMESTAMPTZ
  UNIQUE(tenant_id, email)

departments
  id            UUID PK
  tenant_id     UUID FK→tenants
  name          VARCHAR(100)
  description   TEXT

roles
  id            UUID PK
  tenant_id     UUID FK→tenants   -- NULL 表示全局角色
  name          VARCHAR(50)       -- SUPER_ADMIN / TENANT_ADMIN / DEPT_MANAGER / MEMBER
  permissions   JSONB             -- {"email_accounts": ["read","write"], ...}

user_roles
  user_id       UUID FK→users
  role_id       UUID FK→roles
  department_id UUID FK→departments  -- NULL 表示全租户生效
  PK(user_id, role_id, department_id)
```

### 邮箱账号

```
email_accounts
  id              UUID PK
  tenant_id       UUID FK→tenants
  department_id   UUID FK→departments
  email_address   VARCHAR(200)
  display_name    VARCHAR(100)
  provider        VARCHAR(50)      -- tencent_exmail / netease_exmail / outlook / generic
  imap_host       VARCHAR(200)
  imap_port       INT
  imap_ssl        BOOLEAN
  smtp_host       VARCHAR(200)
  smtp_port       INT
  smtp_ssl        BOOLEAN
  username        VARCHAR(200)
  password_enc    TEXT             -- Fernet 加密
  positioning     VARCHAR(50)      -- sales / hr / support / finance / general
  is_active       BOOLEAN
  last_synced_at  TIMESTAMPTZ
  sync_status     VARCHAR(20)      -- idle / syncing / error
  error_message   TEXT
  created_at      TIMESTAMPTZ

email_account_permissions
  account_id    UUID FK→email_accounts
  user_id       UUID FK→users
  can_read      BOOLEAN
  can_reply     BOOLEAN
  PK(account_id, user_id)
```

### 邮件

```
email_threads
  id            UUID PK
  tenant_id     UUID FK→tenants
  account_id    UUID FK→email_accounts
  subject       VARCHAR(500)
  participants  JSONB      -- [{"email": ..., "name": ...}]
  last_at       TIMESTAMPTZ
  status        VARCHAR(20) -- open / resolved / archived

emails
  id            UUID PK
  tenant_id     UUID FK→tenants
  account_id    UUID FK→email_accounts
  thread_id     UUID FK→email_threads
  message_id    VARCHAR(500) UNIQUE  -- RFC822 Message-ID 去重
  in_reply_to   VARCHAR(500)
  references    TEXT
  direction     VARCHAR(10)   -- inbound / outbound
  from_addr     VARCHAR(500)
  from_name     VARCHAR(200)
  to_addrs      JSONB
  cc_addrs      JSONB
  subject       VARCHAR(500)
  body_text     TEXT
  body_html     TEXT
  language      VARCHAR(10)
  received_at   TIMESTAMPTZ
  created_at    TIMESTAMPTZ
  INDEX(tenant_id, account_id, received_at DESC)
  INDEX(message_id)

email_attachments
  id            UUID PK
  email_id      UUID FK→emails
  tenant_id     UUID FK→tenants
  filename      VARCHAR(500)
  content_type  VARCHAR(100)
  size_bytes    INT
  storage_path  TEXT
  created_at    TIMESTAMPTZ
```

### 分类 & 处理

```
email_classifications
  id              UUID PK
  email_id        UUID FK→emails UNIQUE
  tenant_id       UUID FK→tenants
  email_type      VARCHAR(50)   -- 见类型枚举
  language        VARCHAR(10)
  urgency         SMALLINT      -- 1/2/3
  has_sensitive   BOOLEAN
  sensitive_words JSONB         -- 命中的敏感词列表
  confidence      FLOAT
  llm_model       VARCHAR(100)
  prompt_tokens   INT
  completion_tokens INT
  classified_at   TIMESTAMPTZ

-- 类型枚举:
-- customer_inquiry / quote_request / material_request / complaint
-- payment_reminder / order_confirm / supplier / resume
-- partnership / legal / spam / ad_no_reply / other

email_replies
  id                UUID PK
  email_id          UUID FK→emails
  tenant_id         UUID FK→tenants
  draft_content     TEXT
  final_content     TEXT
  status            VARCHAR(20)  -- pending_review / approved / sent / cancelled
  send_strategy     VARCHAR(20)  -- auto_send / draft_review / human_only
  sent_at           TIMESTAMPTZ
  reviewed_by       UUID FK→users
  reviewed_at       TIMESTAMPTZ
  llm_model         VARCHAR(100)
  rag_chunk_ids     JSONB        -- 检索命中的知识库块 IDs
  attached_asset_ids JSONB       -- 挂载的附件库 IDs
  created_at        TIMESTAMPTZ
```

### 知识库

```
kb_groups
  id            UUID PK
  tenant_id     UUID FK→tenants
  department_id UUID FK→departments  -- NULL 表示全租户
  name          VARCHAR(100)
  category      VARCHAR(50)   -- company_intro / product / faq / support / hr / ...
  positioning   JSONB         -- 适用于哪些邮箱 positioning
  email_types   JSONB         -- 适用于哪些邮件类型
  is_active     BOOLEAN

kb_documents
  id            UUID PK
  tenant_id     UUID FK→tenants
  group_id      UUID FK→kb_groups
  title         VARCHAR(300)
  source_type   VARCHAR(20)   -- pdf / word / excel / txt / manual
  storage_path  TEXT
  status        VARCHAR(20)   -- processing / ready / error
  chunk_count   INT
  created_by    UUID FK→users
  created_at    TIMESTAMPTZ

kb_chunks
  id            UUID PK
  tenant_id     UUID FK→tenants
  document_id   UUID FK→kb_documents
  group_id      UUID FK→kb_groups
  content       TEXT
  chunk_index   INT
  embedding     VECTOR(1536)  -- pgvector
  token_count   INT
  INDEX USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)

asset_library
  id              UUID PK
  tenant_id       UUID FK→tenants
  department_id   UUID FK→departments
  filename        VARCHAR(500)
  content_type    VARCHAR(100)
  size_bytes      INT
  storage_path    TEXT
  description     TEXT
  tags            JSONB        -- 用于 AI 判断相关性
  is_whitelist    BOOLEAN      -- 是否允许自动发送附带
  created_by      UUID FK→users
  created_at      TIMESTAMPTZ
```

### 工单 & 通知

```
tickets
  id            UUID PK
  tenant_id     UUID FK→tenants
  email_id      UUID FK→emails
  account_id    UUID FK→email_accounts
  title         VARCHAR(300)
  reason        VARCHAR(50)   -- sensitive_word / classification / rag_miss / strategy / manual
  status        VARCHAR(20)   -- open / claimed / resolved / closed
  priority      SMALLINT      -- 1/2/3 (映射 urgency)
  assigned_to   UUID FK→users
  created_at    TIMESTAMPTZ
  claimed_at    TIMESTAMPTZ
  resolved_at   TIMESTAMPTZ
  notes         TEXT

ticket_replies
  id            UUID PK
  ticket_id     UUID FK→tickets
  tenant_id     UUID FK→tenants
  author_id     UUID FK→users
  content       TEXT
  reply_sent    BOOLEAN       -- 是否作为邮件发出
  sent_email_id UUID FK→emails
  created_at    TIMESTAMPTZ

notifications
  id            UUID PK
  tenant_id     UUID FK→tenants
  user_id       UUID FK→users
  type          VARCHAR(50)   -- ticket_created / reply_sent / system_error / summary_ready
  title         VARCHAR(200)
  body          TEXT
  is_read       BOOLEAN
  ref_type      VARCHAR(30)   -- ticket / email / report
  ref_id        UUID
  created_at    TIMESTAMPTZ
```

### 审计 & 总结

```
audit_logs
  id            UUID PK
  tenant_id     UUID FK→tenants
  email_id      UUID FK→emails
  stage         VARCHAR(50)   -- received/classified/rag_retrieved/reply_generated/sent/reviewed/human_routed
  actor_type    VARCHAR(20)   -- system / user
  actor_id      UUID          -- NULL if system
  detail        JSONB         -- 本阶段详情（检索 chunks、LLM 调用参数等）
  status        VARCHAR(20)   -- success / failure / skipped
  error_msg     TEXT
  created_at    TIMESTAMPTZ
  INDEX(tenant_id, email_id, created_at)
  INDEX(tenant_id, created_at DESC)

summary_reports
  id            UUID PK
  tenant_id     UUID FK→tenants
  period_type   VARCHAR(10)   -- daily / weekly / monthly
  period_start  DATE
  period_end    DATE
  stats         JSONB         -- 各项统计数字
  pending_tickets JSONB       -- 未闭环清单
  sent_to       JSONB         -- 发送给哪些管理员邮箱
  created_at    TIMESTAMPTZ

sensitive_words
  id            UUID PK
  tenant_id     UUID FK→tenants  -- NULL 表示全局内置
  word          VARCHAR(200)
  category      VARCHAR(50)   -- legal / financial / security / custom
  is_active     BOOLEAN
  created_at    TIMESTAMPTZ
```

### 策略配置

```
email_type_strategies
  id              UUID PK
  tenant_id       UUID FK→tenants
  email_type      VARCHAR(50)   -- 与分类枚举对应
  positioning     VARCHAR(50)   -- 邮箱定位，NULL 表示通用
  send_strategy   VARCHAR(20)   -- auto_send / draft_review / human_only
  kb_group_ids    JSONB         -- 优先使用的知识库分组
  tone            VARCHAR(20)   -- formal / business / concise
  is_active       BOOLEAN
  updated_at      TIMESTAMPTZ
  UNIQUE(tenant_id, email_type, positioning)
```

---

## 3. API 清单

### 认证 `/api/v1/auth`

| Method | Path | 描述 |
|--------|------|------|
| POST | `/auth/login` | 用户名密码登录，返回 JWT access + refresh token |
| POST | `/auth/refresh` | 刷新 access token |
| POST | `/auth/logout` | 注销（黑名单 refresh token） |
| GET  | `/auth/me` | 当前登录用户信息 |

### 租户管理 `/api/v1/tenants` (SUPER_ADMIN)

| Method | Path | 描述 |
|--------|------|------|
| GET | `/tenants` | 列表（超管） |
| POST | `/tenants` | 创建租户 |
| GET | `/tenants/{id}` | 详情 |
| PUT | `/tenants/{id}` | 更新（含 LLM 配置加密存储） |
| DELETE | `/tenants/{id}` | 禁用租户 |

### 用户与权限 `/api/v1/users`

| Method | Path | 权限 | 描述 |
|--------|------|------|------|
| GET | `/users` | TENANT_ADMIN | 租户用户列表 |
| POST | `/users` | TENANT_ADMIN | 创建用户 |
| GET | `/users/{id}` | SELF/ADMIN | 用户详情 |
| PUT | `/users/{id}` | SELF/ADMIN | 更新 |
| DELETE | `/users/{id}` | TENANT_ADMIN | 禁用 |
| GET | `/departments` | ALL | 部门列表 |
| POST | `/departments` | TENANT_ADMIN | 创建部门 |
| PUT | `/departments/{id}` | TENANT_ADMIN | 更新部门 |
| GET | `/roles` | TENANT_ADMIN | 角色列表 |
| POST | `/users/{id}/roles` | TENANT_ADMIN | 分配角色 |

### 邮箱账号 `/api/v1/accounts`

| Method | Path | 权限 | 描述 |
|--------|------|------|------|
| GET | `/accounts` | DEPT_MANAGER+ | 列表（按权限过滤） |
| POST | `/accounts` | TENANT_ADMIN | 绑定邮箱账号 |
| GET | `/accounts/{id}` | PERM | 详情 |
| PUT | `/accounts/{id}` | TENANT_ADMIN | 更新配置 |
| DELETE | `/accounts/{id}` | TENANT_ADMIN | 解绑 |
| POST | `/accounts/{id}/toggle` | TENANT_ADMIN | 启停 |
| POST | `/accounts/{id}/test` | TENANT_ADMIN | 测试 IMAP/SMTP 连通 |
| POST | `/accounts/{id}/sync` | TENANT_ADMIN | 手动触发同步 |

### 邮件 `/api/v1/emails`

| Method | Path | 权限 | 描述 |
|--------|------|------|------|
| GET | `/emails` | MEMBER+ | 收件箱（支持过滤：account/thread/type/status/date） |
| GET | `/emails/{id}` | PERM | 邮件详情（含分类/回复） |
| GET | `/emails/{id}/thread` | PERM | 完整线程 |
| GET | `/emails/{id}/audit` | DEPT_MANAGER+ | 审计链路 |
| POST | `/emails/{id}/classify` | SYSTEM/ADMIN | 手动触发重新分类 |
| POST | `/emails/{id}/generate-reply` | DEPT_MANAGER+ | 手动触发生成草稿 |
| GET | `/emails/export` | DEPT_MANAGER+ | 导出 CSV |

### 回复草稿 `/api/v1/replies`

| Method | Path | 权限 | 描述 |
|--------|------|------|------|
| GET | `/replies` | MEMBER+ | 待审核草稿列表 |
| GET | `/replies/{id}` | PERM | 草稿详情 |
| PUT | `/replies/{id}` | DEPT_MANAGER+ | 编辑草稿内容 |
| POST | `/replies/{id}/approve` | DEPT_MANAGER+ | 审核通过并发送 |
| POST | `/replies/{id}/reject` | DEPT_MANAGER+ | 拒绝草稿 |

### 知识库 `/api/v1/kb`

| Method | Path | 权限 | 描述 |
|--------|------|------|------|
| GET | `/kb/groups` | MEMBER+ | 知识库分组列表 |
| POST | `/kb/groups` | DEPT_MANAGER+ | 创建分组 |
| PUT | `/kb/groups/{id}` | DEPT_MANAGER+ | 更新分组 |
| DELETE | `/kb/groups/{id}` | TENANT_ADMIN | 删除分组 |
| GET | `/kb/documents` | MEMBER+ | 文档列表 |
| POST | `/kb/documents` | DEPT_MANAGER+ | 上传文档（multipart） |
| POST | `/kb/documents/manual` | DEPT_MANAGER+ | 手工录入话术 |
| DELETE | `/kb/documents/{id}` | DEPT_MANAGER+ | 删除文档 |
| GET | `/kb/search` | MEMBER+ | 语义搜索测试 |
| GET | `/assets` | MEMBER+ | 附件库列表 |
| POST | `/assets` | DEPT_MANAGER+ | 上传附件 |
| PUT | `/assets/{id}` | DEPT_MANAGER+ | 更新标签/白名单 |
| DELETE | `/assets/{id}` | DEPT_MANAGER+ | 删除 |

### 工单 `/api/v1/tickets`

| Method | Path | 权限 | 描述 |
|--------|------|------|------|
| GET | `/tickets` | MEMBER+ | 工单列表（含过滤） |
| GET | `/tickets/{id}` | PERM | 工单详情 |
| POST | `/tickets/{id}/claim` | MEMBER+ | 认领工单 |
| POST | `/tickets/{id}/reply` | MEMBER+ | 添加备注/回复邮件 |
| POST | `/tickets/{id}/resolve` | MEMBER+ | 闭环工单 |
| POST | `/tickets/{id}/close` | DEPT_MANAGER+ | 强制关闭 |

### 通知 `/api/v1/notifications`

| Method | Path | 描述 |
|--------|------|------|
| GET | `/notifications` | 当前用户通知列表 |
| POST | `/notifications/{id}/read` | 标已读 |
| POST | `/notifications/read-all` | 全部已读 |

### 策略配置 `/api/v1/settings`

| Method | Path | 权限 | 描述 |
|--------|------|------|------|
| GET | `/settings/strategies` | TENANT_ADMIN | 邮件类型处理策略 |
| PUT | `/settings/strategies/{email_type}` | TENANT_ADMIN | 更新策略 |
| GET | `/settings/sensitive-words` | TENANT_ADMIN | 敏感词列表 |
| POST | `/settings/sensitive-words` | TENANT_ADMIN | 添加敏感词 |
| DELETE | `/settings/sensitive-words/{id}` | TENANT_ADMIN | 删除敏感词 |
| GET | `/settings/llm` | TENANT_ADMIN | LLM 配置（脱敏） |
| PUT | `/settings/llm` | TENANT_ADMIN | 更新 LLM 配置 |
| GET | `/settings/summary` | TENANT_ADMIN | 定时总结配置 |
| PUT | `/settings/summary` | TENANT_ADMIN | 更新定时总结配置 |

### 报表 `/api/v1/reports`

| Method | Path | 权限 | 描述 |
|--------|------|------|------|
| GET | `/reports/stats` | DEPT_MANAGER+ | 实时统计（今日/本周） |
| GET | `/reports/summaries` | TENANT_ADMIN | 定时总结历史 |
| GET | `/reports/summaries/{id}` | TENANT_ADMIN | 总结详情 |
| POST | `/reports/summaries/generate` | TENANT_ADMIN | 手动触发生成 |
| GET | `/reports/audit` | DEPT_MANAGER+ | 审计日志查询 |
| GET | `/reports/audit/export` | TENANT_ADMIN | 审计日志 CSV 导出 |

### Webhook (预留) `/api/v1/webhooks`

| Method | Path | 描述 |
|--------|------|------|
| GET | `/webhooks` | 已配置 webhook 列表（结构预留，二期实现） |
| POST | `/webhooks` | 添加 webhook（结构预留） |

---

## 4. 关键设计决策

### LLM Provider 抽象

```python
class BaseLLMProvider(ABC):
    async def chat(self, messages, **kwargs) -> LLMResponse: ...
    async def embed(self, texts: list[str]) -> list[list[float]]: ...

# 实现: AnthropicProvider / OpenAIProvider / DeepSeekProvider
# 配置在 tenant.settings.llm_config 中，按租户隔离
```

### 邮件 Provider 抽象

```python
class BaseMailProvider(ABC):
    async def connect(self) -> None: ...
    async def fetch_new(self, since: datetime) -> list[RawEmail]: ...
    async def send(self, msg: OutboundEmail) -> str: ...
    async def idle_listen(self, callback) -> None: ...

# 实现: IMAPSMTPProvider (通用), 可按 provider 字段做特化配置
```

### 敏感词阻断（优先级最高）

```python
# 在任何 LLM 调用之前执行
def check_sensitive(text: str, words: list[str]) -> list[str]:
    # 全文本匹配（subject + body），大小写不敏感
    # 命中 → 立即创建工单，写 audit_log stage=sensitive_blocked，return
    # 不进入分类/RAG/生成流程
```

### ARQ 任务队列

```
Tasks:
  poll_inbox(account_id)          -- 每 5 分钟轮询兜底 (+ IMAP IDLE 实时)
  process_email(email_id)         -- 核心流水线（分类→RAG→生成→路由）
  send_reply(reply_id)            -- 发送邮件
  generate_summary(tenant_id, period)  -- 定时总结
  reindex_document(document_id)   -- 知识库文档分块 embedding

CronJobs (ARQ Cron):
  daily_summary   -- 每天 08:00
  weekly_summary  -- 每周一 08:00
  monthly_summary -- 每月 1 日 08:00
```

### 加密存储

- 邮箱授权码：`cryptography.fernet.Fernet` 对称加密
- Fernet 主密钥从环境变量 `ENCRYPTION_KEY` 读取（base64 编码的 32 字节）
- LLM API Key 同样 Fernet 加密后存入 `tenant.settings` JSONB

---

## 5. 项目目录结构

```
d:\add\
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI app 入口
│   │   ├── config.py                  # 环境变量 Settings (pydantic-settings)
│   │   ├── db/
│   │   │   ├── base.py                # SQLAlchemy engine / session
│   │   │   ├── models/                # ORM 模型
│   │   │   └── migrations/            # Alembic
│   │   ├── api/
│   │   │   ├── deps.py                # FastAPI Dependencies (auth, tenant, perm)
│   │   │   └── v1/                    # 路由
│   │   ├── core/
│   │   │   ├── security.py            # JWT / Fernet
│   │   │   ├── permissions.py         # RBAC 守卫
│   │   │   └── exceptions.py          # 统一异常
│   │   ├── services/
│   │   │   ├── mail/                  # IMAP/SMTP provider 抽象 + 实现
│   │   │   ├── llm/                   # LLM provider 抽象 + 实现
│   │   │   ├── pipeline/              # 核心流水线步骤
│   │   │   │   ├── classifier.py
│   │   │   │   ├── rag.py
│   │   │   │   ├── reply_generator.py
│   │   │   │   └── router.py
│   │   │   ├── kb/                    # 知识库 ingestion / 检索
│   │   │   ├── ticket.py
│   │   │   ├── notification.py
│   │   │   └── summary.py
│   │   ├── repos/                     # 仓储层 (带 tenant_id 过滤)
│   │   └── worker/
│   │       ├── tasks.py               # ARQ 任务定义
│   │       └── crons.py               # 定时任务
│   ├── tests/
│   │   ├── test_pipeline.py
│   │   ├── test_sensitive.py
│   │   ├── test_permissions.py
│   │   └── conftest.py
│   ├── scripts/
│   │   └── seed.py
│   ├── alembic.ini
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/                       # Next.js App Router
│   │   ├── components/
│   │   └── lib/
│   ├── package.json
│   └── tailwind.config.ts
├── docker-compose.yml
├── .env.example
└── README.md
```
