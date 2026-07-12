from arq import create_pool
from arq.connections import RedisSettings
from arq.cron import cron

from app.config import settings
from app.worker.tasks import (
    escalate_tickets,
    generate_summary,
    ingest_document,
    poll_all_accounts,
    poll_inbox,
    process_email,
    run_campaigns,
    send_reply,
    send_scheduled,
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
                 ingest_document, escalate_tickets, run_campaigns, send_scheduled,
                 daily_summary, weekly_summary, monthly_summary]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    max_jobs = settings.WORKER_MAX_JOBS
    job_timeout = 300
    retry_jobs = True
    max_tries = 3
    cron_jobs = [
        cron(poll_all_accounts),  # every minute (second=0) for near-real-time inbox
        cron(escalate_tickets, minute={0, 30}),
        cron(run_campaigns, minute={15, 45}),
        cron(send_scheduled),  # every minute (second=0)
        cron(daily_summary, hour=8, minute=0),
        cron(weekly_summary, weekday=0, hour=8, minute=0),
        cron(monthly_summary, day=1, hour=8, minute=0),
    ]
