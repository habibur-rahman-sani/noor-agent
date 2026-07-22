from agno.team.team import Team
from config import get_model, get_db, MEMORY_KWARGS
from agents.scheduler_agent import scheduler_agent

team = Team(
    name="Scheduler Team",
    mode="coordinate",
    model=get_model("general"),
    db=get_db(),
    members=[scheduler_agent],
    instructions=[
        "ভবিষ্যতের/পুনরাবৃত্ত/রিমাইন্ডার-টাইপ যেকোনো কাজ (শিডিউল, cron, নির্দিষ্ট সময়ে কিছু করা) -> Scheduler Agent।",
    ],
    markdown=True,
    **MEMORY_KWARGS,
)
