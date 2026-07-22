from agno.team.team import Team
from config import get_model, get_db, MEMORY_KWARGS
from agents.research_agent import research_agent
from agents.data_agent import data_agent
from agents.finance_agent import finance_agent

team = Team(
    name="Knowledge Team",
    mode="coordinate",
    model=get_model("general"),
    db=get_db(),
    members=[research_agent, data_agent, finance_agent],
    instructions=[
        "তথ্য অনুসন্ধান -> Research Agent। ডেটা প্রসেসিং -> Data Agent। স্টক/ফাইন্যান্স -> Finance Agent।",
    ],
    markdown=True,
    **MEMORY_KWARGS,
)
