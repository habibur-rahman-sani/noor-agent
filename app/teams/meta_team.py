from agno.team.team import Team
from config import get_model, get_db, MEMORY_KWARGS
from agents.meta_agent import meta_agent

team = Team(
    name="Meta Team",
    mode="coordinate",
    model=get_model("coding"),
    db=get_db(),
    members=[meta_agent],
    instructions=[
        "সিস্টেমকে নতুন Team/Agent দিয়ে প্রসারিত করার (self-extension) যেকোনো কাজ -> Meta Agent।",
        "এটা সবচেয়ে ঝুঁকিপূর্ণ টিম — সবসময় approval-flow অনুসরণ করা হচ্ছে কিনা নিশ্চিত করো।",
    ],
    markdown=True,
    **MEMORY_KWARGS,
)
