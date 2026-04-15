"""APScheduler bootstrap. Phase 2 jobs (weekly discovery, analytics sync) register here."""
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()

# Phase 2:
# scheduler.add_job(run_weekly_discovery, "cron", day_of_week="mon", hour=6)
# scheduler.add_job(sync_daily_analytics, "cron", hour=3)
