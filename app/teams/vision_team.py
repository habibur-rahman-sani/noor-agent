from agno.team.team import Team
from config import get_model, get_db, MEMORY_KWARGS
from agents.vision_agent import vision_agent

team = Team(
    name="Vision Team",
    mode="coordinate",
    model=get_model("general"),
    db=get_db(),
    members=[vision_agent],
    instructions=[
        "স্ক্রিনশট নেওয়া বা স্ক্রিনে কী আছে তা পড়ার (OCR) যেকোনো কাজ -> Vision Agent।",
        "এই টিম শুধু GUI/ডিসপ্লে থাকা মেশিনে কাজ করবে, headless সার্ভারে না।",
    ],
    markdown=True,
    **MEMORY_KWARGS,
)
