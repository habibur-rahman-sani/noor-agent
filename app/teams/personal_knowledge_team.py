from agno.team.team import Team
from config import get_model, get_db, MEMORY_KWARGS
from agents.personal_knowledge_agent import personal_knowledge_agent

team = Team(
    name="Personal Knowledge Team",
    mode="coordinate",
    model=get_model("research"),
    db=get_db(),
    members=[personal_knowledge_agent],
    instructions=[
        "ইউজারের নিজস্ব নোট/ডকুমেন্ট (PERSONAL_DOCS_DIR) নিয়ে প্রশ্নের জন্য -> Personal Knowledge Agent।",
        "সাধারণ ওয়েব-ভিত্তিক রিসার্চের জন্য Knowledge Team ব্যবহার করা ভালো, এটা শুধু ব্যক্তিগত ফাইলের জন্য।",
    ],
    markdown=True,
    **MEMORY_KWARGS,
)
