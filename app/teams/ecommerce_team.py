from agno.team.team import Team
from config import get_model, get_db, MEMORY_KWARGS
from agents.ecommerce_agent import ecommerce_agent

team = Team(
    name="E-commerce Team",
    mode="coordinate",
    model=get_model("social"),
    db=get_db(),
    members=[ecommerce_agent],
    instructions=["প্রোডাক্ট/অর্ডার/ইনভেন্টরি/স্টোর ম্যানেজমেন্ট -> E-commerce Agent।"],
    markdown=True,
    **MEMORY_KWARGS,
)
