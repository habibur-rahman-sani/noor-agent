from agno.agent import Agent
from config import get_model, get_db, MEMORY_KWARGS
from tools_free import DATA_TOOLS, SYSTEM_TOOLS

data_agent = Agent(
    name="Data Agent",
    role="CSV/SQL/DataFrame নিয়ে কাজ করে, ক্যালকুলেশন করে, চার্ট/ভিজুয়ালাইজেশন বানায়",
    model=get_model("reasoning"),
    db=get_db(),
    tools=DATA_TOOLS + [t for t in SYSTEM_TOOLS if t.name in ("calculator_tools", "python_tools")],
    instructions=[
        "ডেটা প্রসেসিং করার আগে ডেটার শেপ/টাইপ বুঝে নাও।",
        "সম্ভব হলে ফলাফল টেবিল বা চার্ট আকারে দেখাও।",
    ],
    markdown=True,
    **MEMORY_KWARGS,
)
