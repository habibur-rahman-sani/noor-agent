from agno.agent import Agent
from config import get_model, get_db, has_key, MEMORY_KWARGS

prod_tools = []

if has_key("NOTION_TOKEN"):
    from agno.tools.notion import NotionTools
    prod_tools.append(NotionTools())

if has_key("GOOGLE_CALENDAR_CREDENTIALS_PATH"):
    from agno.tools.googlecalendar import GoogleCalendarTools
    prod_tools.append(GoogleCalendarTools())

productivity_agent = Agent(
    name="Productivity Agent",
    role="Notion পেজ, Google Calendar ইভেন্ট ম্যানেজ করে",
    model=get_model("general"),
    db=get_db(),
    tools=prod_tools,
    instructions=["ডেটা তৈরি/এডিট/ডিলিটের আগে কনফার্ম নাও।", "কোন সার্ভিস কানেক্টেড নেই সেটা বলো।"],
    markdown=True,
    **MEMORY_KWARGS,
)

if not prod_tools:
    print("⚠️  Productivity Agent-এ কোনো টুল সক্রিয় নেই — .env-এ NOTION_TOKEN / GOOGLE_CALENDAR_CREDENTIALS_PATH বসাও।")
