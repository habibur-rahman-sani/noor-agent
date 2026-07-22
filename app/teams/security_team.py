from agno.team.team import Team
from config import get_model, get_db, MEMORY_KWARGS
from agents.security_agent import security_agent

team = Team(
    name="Security Team",
    mode="coordinate",
    model=get_model("general"),
    db=get_db(),
    members=[security_agent],
    instructions=[
        "স্পর্শকাতর তথ্য (key/পাসওয়ার্ড) সেভ/পড়া, বা পেন্ডিং approval-request দেখার কাজ -> Security Agent।",
    ],
    markdown=True,
    **MEMORY_KWARGS,
)
