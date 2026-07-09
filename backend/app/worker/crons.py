from arq.cron import cron


CRON_JOBS = [
    cron("poll_all_accounts", minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}),
    cron("daily_summary", hour=8, minute=0),
    cron("weekly_summary", weekday=0, hour=8, minute=0),
    cron("monthly_summary", day=1, hour=8, minute=0),
]
