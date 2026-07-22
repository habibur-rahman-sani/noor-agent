from agno.team.team import Team
from config import get_model, get_db, MEMORY_KWARGS
from agents.media_gen_agent import media_gen_agent

team = Team(
    name="Media Generation Team",
    mode="coordinate",
    model=get_model("creative"),
    db=get_db(),
    members=[media_gen_agent],
    instructions=[
        "ছবি/ভিডিও তৈরির যেকোনো কাজ -> Media Generation Agent।",
    ],
    markdown=True,
    **MEMORY_KWARGS,
)
