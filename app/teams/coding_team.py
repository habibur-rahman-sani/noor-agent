from agno.team.team import Team
from config import get_model, get_db, MEMORY_KWARGS
from agents.coding_agent import coding_agent

team = Team(
    name="Coding Team",
    mode="coordinate",
    model=get_model("coding"),
    db=get_db(),
    members=[coding_agent],
    instructions=[
        "যেকোনো কোডিং/সফটওয়্যার ডেভেলপমেন্ট কাজ (লেখা, রান, ডিবাগ, রিপো ম্যানেজমেন্ট, সন্ডবক্স) -> Coding Agent।",
        "কোডিং না হলে (যেমন সাধারণ তথ্য অনুসন্ধান) সেটা এই টিমের কাজ না, সুপারভাইজারকে অন্য টিমে পাঠাতে বলো।",
    ],
    markdown=True,
    **MEMORY_KWARGS,
)
