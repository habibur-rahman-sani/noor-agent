from agno.team.team import Team
from config import get_model, get_db, MEMORY_KWARGS
from agents.linux_system_agent import linux_system_agent

team = Team(
    name="Linux System Team",
    mode="coordinate",
    model=get_model("coding"),
    db=get_db(),
    members=[linux_system_agent],
    instructions=[
        "Linux প্যাকেজ ম্যানেজমেন্ট (ইনস্টল/রিমুভ/আপডেট) ও systemd সার্ভিস ম্যানেজমেন্ট -> Linux System Agent।",
    ],
    markdown=True,
    **MEMORY_KWARGS,
)
