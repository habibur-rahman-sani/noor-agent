from agno.team.team import Team
from config import get_model, get_db, MEMORY_KWARGS
from agents.notification_agent import notification_agent

team = Team(
    name="Notification Team",
    mode="coordinate",
    model=get_model("general"),
    db=get_db(),
    members=[notification_agent],
    instructions=[
        "ডিভাইসে নোটিফিকেশন পাঠানোর যেকোনো কাজ -> Notification Agent।",
    ],
    markdown=True,
    **MEMORY_KWARGS,
)
