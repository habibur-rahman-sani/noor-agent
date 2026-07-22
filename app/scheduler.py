"""
scheduler.py
============
"Proactive layer" — Jarvis-টাইপ AI-কে শুধু জিজ্ঞেস করলে উত্তর দেওয়ার বদলে
নিজে থেকে নির্দিষ্ট সময়ে/পুনরাবৃত্তিতে কাজ করাতে হলে এই মডিউল দরকার।

APScheduler ব্যবহার করা হয়েছে, MongoDB job-store দিয়ে — মানে সার্ভার রিস্টার্ট
হলেও শিডিউল করা কাজ হারিয়ে যায় না। প্রতিটা জব ফায়ার হলে supervisor-কে
সেই prompt দিয়ে চালানো হয় এবং ফলাফল ডেস্কটপ নোটিফিকেশন + DB-তে লগ হয়।

চালু হয় server.py-র FastAPI startup event থেকে (`start_scheduler()`), CLI-only
(main.py) মোডে scheduler চালু হয় না।
"""

import os
import logging
from datetime import datetime, timezone

logger = logging.getLogger("agno-scheduler")

_scheduler = None


def _mongo_url() -> str:
    return os.getenv("MONGODB_URI", "mongodb://localhost:27017")


def _db_name() -> str:
    return os.getenv("MONGODB_DB_NAME", "agno_system")


def get_scheduler():
    """সিঙ্গলটন APScheduler ইনস্ট্যান্স — ল্যাজি-ইনিশিয়ালাইজড।"""
    global _scheduler
    if _scheduler is None:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.jobstores.mongodb import MongoDBJobStore

        jobstores = {
            "default": MongoDBJobStore(
                database=_db_name(), collection="agno_scheduler_jobs", host=_mongo_url()
            )
        }
        _scheduler = BackgroundScheduler(jobstores=jobstores, timezone="UTC")
    return _scheduler


def start_scheduler():
    sched = get_scheduler()
    if not sched.running:
        sched.start()
        logger.info("Proactive scheduler চালু হয়েছে (MongoDB job-store)।")
    return sched


def _run_scheduled_prompt(prompt: str, job_label: str):
    """একটা শিডিউল করা কাজ ফায়ার হলে এটা চলে — supervisor-কে prompt দিয়ে
    সিঙ্ক্রোনাসভাবে চালায় (APScheduler-এর ডিফল্ট থ্রেড-পুল এক্সিকিউটর), ফলাফল
    লগ করে এবং সম্ভব হলে ডেস্কটপ নোটিফিকেশন পাঠায়।"""
    from supervisor import supervisor

    try:
        response = supervisor.run(prompt, session_id=f"scheduled::{job_label}")
        text = getattr(response, "content", None) or str(response)
    except Exception as e:  # noqa: BLE001
        text = f"শিডিউল করা কাজ ব্যর্থ হয়েছে: {e}"
        logger.exception("Scheduled job failed: %s", job_label)

    try:
        from pymongo import MongoClient
        MongoClient(_mongo_url())[_db_name()]["agno_scheduler_results"].insert_one({
            "job_label": job_label, "prompt": prompt, "result": text,
            "ran_at": datetime.now(timezone.utc),
        })
    except Exception:
        pass

    try:
        from notification_core import send_desktop_notification
        send_desktop_notification(f"AI OS — {job_label}", text[:200])
    except Exception:
        pass


# ---------------------------------------------------------- agent-facing ---

from agno.tools.toolkit import Toolkit


class SchedulerTools(Toolkit):
    """এজেন্ট এই টুল দিয়ে ভবিষ্যতের জন্য এক-বারের বা পুনরাবৃত্ত কাজ শিডিউল করতে পারে
    (রিমাইন্ডার, পর্যায়ক্রমিক চেক-আপ, ভবিষ্যতে কোনো prompt আবার supervisor-কে পাঠানো)।
    """

    def __init__(self, **kwargs):
        super().__init__(
            name="scheduler_tools",
            tools=[self.schedule_once, self.schedule_recurring, self.list_scheduled_jobs, self.cancel_scheduled_job],
            **kwargs,
        )

    def schedule_once(self, job_label: str, prompt: str, run_at_iso: str) -> str:
        """একবারের জন্য ভবিষ্যতের একটা নির্দিষ্ট সময়ে supervisor-কে prompt দিয়ে চালাও।

        Args:
            job_label: শিডিউলের একটা ছোট নাম/আইডি
            prompt: যেই মেসেজ supervisor-কে পাঠানো হবে (যেমন "আজকের ইমেইল চেক করো")
            run_at_iso: কখন চলবে, ISO 8601 ফরম্যাটে UTC (যেমন "2026-07-21T09:00:00")
        """
        from datetime import datetime as dt
        sched = start_scheduler()
        run_time = dt.fromisoformat(run_at_iso)
        sched.add_job(_run_scheduled_prompt, "date", run_date=run_time,
                       args=[prompt, job_label], id=job_label, replace_existing=True)
        return f"শিডিউল হয়েছে: '{job_label}' -> {run_at_iso} (UTC)"

    def schedule_recurring(self, job_label: str, prompt: str, cron_expression: str) -> str:
        """cron এক্সপ্রেশন দিয়ে পুনরাবৃত্ত কাজ শিডিউল করো।

        Args:
            job_label: শিডিউলের একটা ছোট নাম/আইডি
            prompt: যেই মেসেজ supervisor-কে বারবার পাঠানো হবে
            cron_expression: স্ট্যান্ডার্ড ৫-ফিল্ড cron (মিনিট ঘণ্টা দিন মাস সপ্তাহেরদিন),
                যেমন "0 9 * * *" মানে প্রতিদিন সকাল ৯টায় UTC
        """
        from apscheduler.triggers.cron import CronTrigger
        sched = start_scheduler()
        trigger = CronTrigger.from_crontab(cron_expression, timezone="UTC")
        sched.add_job(_run_scheduled_prompt, trigger, args=[prompt, job_label],
                       id=job_label, replace_existing=True)
        return f"পুনরাবৃত্ত শিডিউল হয়েছে: '{job_label}' -> cron '{cron_expression}' (UTC)"

    def list_scheduled_jobs(self) -> str:
        """সব শিডিউল করা কাজের তালিকা দেখাও।"""
        sched = start_scheduler()
        jobs = sched.get_jobs()
        if not jobs:
            return "কোনো শিডিউল করা কাজ নেই।"
        return "\n".join(f"- {j.id}: পরের রান {j.next_run_time}" for j in jobs)

    def cancel_scheduled_job(self, job_label: str) -> str:
        """একটা শিডিউল করা কাজ বাতিল করো।

        Args:
            job_label: যেই জব বাতিল করতে হবে তার label/id
        """
        sched = start_scheduler()
        try:
            sched.remove_job(job_label)
            return f"'{job_label}' বাতিল হয়েছে।"
        except Exception as e:  # noqa: BLE001
            return f"বাতিল করা যায়নি: {e}"
