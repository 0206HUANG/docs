# 企业邮箱 AI 托管系统

AI-powered enterprise email management SaaS — automatically classifies, retrieves knowledge, generates replies, and routes emails based on configurable rules.

## Quick Start (Docker)

### 1. Clone and configure

```bash
cp .env.example .env
# Edit .env: set SECRET_KEY and ENCRYPTION_KEY
# Generate ENCRYPTION_KEY: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 2. Start all services

```bash
docker-compose up -d
```

This automatically:
- Starts PostgreSQL 16 + pgvector, Redis
- Runs `alembic upgrade head` (creates schema)
- Runs `python scripts/seed.py` (demo data)
- Starts FastAPI app on port 8000
- Starts ARQ worker
- Starts Next.js frontend on port 3000

### 3. Access

| Service | URL |
|---------|-----|
| API docs | http://localhost:8000/docs |
| Frontend | http://localhost:3000 |
| Demo login | admin@demo.emailai.local / Admin@123456 |

## Architecture

```
IMAP (aioimaplib) → ARQ Queue → Pipeline → PostgreSQL + pgvector
                                         → SMTP (aiosmtplib)
```

**Pipeline flow per email:**
1. Sensitive word check (highest priority — immediate human queue if matched)
2. LLM classification (type / language / urgency)
3. RAG retrieval (pgvector similarity search against knowledge base)
4. Reply generation (LLM, grounded in KB, no hallucination)
5. Route decision (auto_send / draft_review / human_only)
6. Audit logging (every step recorded)

## Configuration

### LLM Providers

Set via Admin UI → Settings → LLM Config:

| Provider | `provider` value | Notes |
|----------|-----------------|-------|
| OpenAI | `openai` | Default |
| Anthropic | `anthropic` | Embeddings via OpenAI |
| DeepSeek | `deepseek` | OpenAI-compatible |

### Email Providers

Configure IMAP/SMTP per account. Supported:
- 腾讯企业邮 (imap.exmail.qq.com)
- 网易企业邮 (imap.qiye.163.com)
- Outlook (outlook.office365.com)
- Any standard IMAP/SMTP server

### Sensitive Words

Built-in words: 诉讼、起诉、律师函、赔偿、转账 etc.
Add custom words via Admin UI → Settings → Sensitive Words.

## Development

### Backend

```bash
cd backend
pip install -r requirements.txt
# Set env vars
uvicorn app.main:app --reload
```

### Run tests

```bash
cd backend
pytest tests/ -v
```

### Worker

```bash
cd backend
python -m arq app.worker.main.WorkerSettings
```

### Run migrations

```bash
cd backend
alembic upgrade head
```

## RBAC

| Role | Capabilities |
|------|-------------|
| SUPER_ADMIN | Manage all tenants |
| TENANT_ADMIN | Manage users, accounts, settings, strategies |
| DEPT_MANAGER | Manage KB, review drafts, view reports |
| MEMBER | View emails, handle tickets |

## Security

- Passwords: bcrypt hashed
- Email passwords / API keys: Fernet symmetric encryption (`ENCRYPTION_KEY`)
- JWT auth: RS256-signed access + refresh tokens
- Tenant isolation: all queries filtered by `tenant_id` at repository layer
- Sensitive word blocking: runs before any LLM call, cannot be bypassed

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL async URL | ✅ |
| `REDIS_URL` | Redis URL | ✅ |
| `SECRET_KEY` | JWT signing key | ✅ |
| `ENCRYPTION_KEY` | Fernet key for secrets | ✅ |
| `STORAGE_PATH` | File storage directory | ✅ |
| `DEBUG` | Enable debug logging | ❌ |
