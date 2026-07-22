from agno.team.team import Team
from config import get_model, get_db, MEMORY_KWARGS
from agents.browser_agent import browser_agent

team = Team(
    name="Automation Team",
    mode="coordinate",
    model=get_model("general"),
    db=get_db(),
    members=[browser_agent],
    instructions=["ওয়েব ব্রাউজিং/স্ক্র্যাপিং/ইন্টারঅ্যাকশন -> Browser Agent।"],
    markdown=True,
    **MEMORY_KWARGS,
)
