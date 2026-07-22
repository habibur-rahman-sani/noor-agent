from agno.team.team import Team
from config import get_model, get_db, MEMORY_KWARGS
from agents.pc_agent import pc_agent

team = Team(
    name="PC Team",
    mode="coordinate",
    model=get_model("coding"),
    db=get_db(),
    members=[pc_agent],
    instructions=["কম্পিউটার/OS-লেভেল অটোমেশন ও কাজ -> PC Agent।"],
    markdown=True,
    **MEMORY_KWARGS,
)
