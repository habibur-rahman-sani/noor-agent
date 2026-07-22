from agno.agent import Agent
from config import get_model, get_db, has_key, MEMORY_KWARGS
from tools_free import SCRAPE_TOOLS

browser_tools = list(SCRAPE_TOOLS)

from agno.tools.webbrowser import WebBrowserTools
browser_tools.append(WebBrowserTools())

if has_key("BROWSERBASE_API_KEY", "BROWSERBASE_PROJECT_ID"):
    from agno.tools.browserbase import BrowserbaseTools
    browser_tools.append(BrowserbaseTools())

if has_key("AGENTQL_API_KEY"):
    from agno.tools.agentql import AgentQLTools
    browser_tools.append(AgentQLTools())

browser_agent = Agent(
    name="Browser Agent",
    role="ওয়েবসাইট ব্রাউজ করে, কনটেন্ট বের করে, প্রয়োজনে ফর্ম ফিলাপ/ক্লিক করে",
    model=get_model("general"),
    db=get_db(),
    tools=browser_tools,
    instructions=[
        "লগইন/পারসোনাল ডেটা ইনভলভড অ্যাকশনের আগে কনফার্ম নাও।",
        "BROWSERBASE/AGENTQL key না থাকলে জটিল ইন্টারঅ্যাকশন সম্ভব না, সেটা জানাও।",
    ],
    markdown=True,
    **MEMORY_KWARGS,
)
