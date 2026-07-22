from agno.team.team import Team
from config import get_model, get_db, MEMORY_KWARGS
from agents.communication_agent import communication_agent
from agents.productivity_agent import productivity_agent
from agents.media_agent import media_agent

team = Team(
    name="Operations Team",
    mode="coordinate",
    model=get_model("general"),
    db=get_db(),
    members=[communication_agent, productivity_agent, media_agent],
    instructions=[
        "মেসেজ (Slack/Gmail/Email) -> Communication Agent।",
        "Notion/Calendar -> Productivity Agent।",
        "ইমেজ/অডিও/ভিডিও জেনারেশন -> Media Agent।",
    ],
    markdown=True,
    **MEMORY_KWARGS,
)
