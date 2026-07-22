from agno.team.team import Team
from config import get_model, get_db, MEMORY_KWARGS
from agents.iot_agent import iot_agent

team = Team(
    name="IoT Team",
    mode="coordinate",
    model=get_model("general"),
    db=get_db(),
    members=[iot_agent],
    instructions=[
        "স্মার্ট হোম ডিভাইস (লাইট/প্লাগ/থার্মোস্ট্যাট) নিয়ন্ত্রণের যেকোনো কাজ -> IoT Agent।",
    ],
    markdown=True,
    **MEMORY_KWARGS,
)
