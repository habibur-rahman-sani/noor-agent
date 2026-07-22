from agno.agent import Agent
from config import get_model, get_db, MEMORY_KWARGS
from tools_free import FINANCE_TOOLS, SEARCH_TOOLS

finance_agent = Agent(
    name="Finance Agent",
    role="স্টক প্রাইস, কোম্পানি তথ্য, এনালিস্ট রেকমেন্ডেশন নিয়ে কাজ করে",
    model=get_model("research"),
    db=get_db(),
    tools=FINANCE_TOOLS + [t for t in SEARCH_TOOLS if t.name == "duckduckgo_tools"],
    instructions=["এটা বিনিয়োগ পরামর্শ না — শুধু তথ্য, সেটা মনে করিয়ে দাও।"],
    markdown=True,
    **MEMORY_KWARGS,
)
