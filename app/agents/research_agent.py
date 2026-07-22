from agno.agent import Agent
from config import get_model, get_db, MEMORY_KWARGS
from tools_free import SEARCH_TOOLS, SCRAPE_TOOLS, MISC_TOOLS

research_agent = Agent(
    name="Research Agent",
    role="ওয়েব, উইকিপিডিয়া, arXiv, PubMed, HackerNews থেকে তথ্য খুঁজে বের করে ও যাচাই করে",
    model=get_model("research"),
    db=get_db(),
    tools=SEARCH_TOOLS + SCRAPE_TOOLS + [t for t in MISC_TOOLS if t.name == "reasoning_tools"],
    instructions=[
        "প্রতিটা তথ্যের সোর্স উল্লেখ করো।",
        "একাধিক সোর্স মিলিয়ে যাচাই করে উত্তর দাও।",
        "নতুন/সাম্প্রতিক তথ্যের জন্য সবসময় সার্চ করো।",
    ],
    markdown=True,
    **MEMORY_KWARGS,
)
