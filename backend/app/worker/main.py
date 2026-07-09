from arq import create_pool
from arq.connections import RedisSettings

from app.config import settings
from app.worker.tasks import (
    generate_summary,
    ingest_document,
    poll_all_accounts,
    poll_inbox,
    process_email,
    send_reply,
)


async def daily_summary(ctx):
    from arq import ArqRedis
    async with ctx["redis"].pipeline() as pipe:
        pass
    from app.worker.tasks import generate_summary
    from app.db.base import AsyncSessionLocal
    from sqlalchemy import select
    from app.db.models import Tenant
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Tenant).where(Tenant.is_active == True))
        for tenant in result.scalars():
            await ctx["redis"].enqueue_job("generate_summary", str(tenant.id), "daily")


async def weekly_summary(ctx):
    from app.db.base import AsyncSessionLocal
    from sqlalchemy import select
    from app.db.models import Tenant
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Tenant).where(Tenant.is_active == True))
        for tenant in result.scalars():
            await ctx["redis"].enqueue_job("generate_summary", str(tenant.id), "weekly")


async def monthly_summary(ctx):
    from app.db.base import AsyncSessionLocal
    from sqlalchemy import select
    from app.db.models import Tenant
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Tenant).where(Tenant.is_active == True))
        for tenant in result.scalars():
            await ctx["redis"].enqueue_job("generate_summary", str(tenant.id), "monthly")


class WorkerSettings:
    functions = [poll_inbox, process_email, send_reply, generate_summary, poll_all_accounts,
                 ingest_document, daily_summary, weekly_summary, monthly_summary]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    max_jobs = settings.WORKER_MAX_JOBS
    job_timeout = 300
    retry_jobs = True
    max_tries = 3
    cron_jobs = [
        {"name": "poll_all_accounts", "coroutine": poll_all_accounts, "minute": {0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}},
        {"name": "daily_summary", "coroutine": daily_summary, "hour": 8, "minute": 0},
        {"name": "weekly_summary", "coroutine": weekly_summary, "weekday": 0, "hour": 8, "minute": 0},
        {"name": "monthly_summary", "coroutine": monthly_summary, "day": 1, "hour": 8, "minute": 0},
    ]
