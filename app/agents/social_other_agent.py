"""অন্যান্য সোশ্যাল প্ল্যাটফর্ম — X, Reddit, Discord, WhatsApp (সব key-নির্ভর, ঐচ্ছিক)"""
from agno.agent import Agent
from config import get_model, get_db, has_key, MEMORY_KWARGS

other_tools = []

if has_key("X_API_KEY"):
    from agno.tools.x import XTools
    other_tools.append(XTools())

if has_key("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET"):
    from agno.tools.reddit import RedditTools
    other_tools.append(RedditTools())

if has_key("DISCORD_TOKEN"):
    from agno.tools.discord import DiscordTools
    other_tools.append(DiscordTools())

if has_key("WHATSAPP_ACCESS_TOKEN"):
    from agno.tools.whatsapp import WhatsAppTools
    other_tools.append(WhatsAppTools())

social_other_agent = Agent(
    name="Other Social Agent",
    role="X (Twitter), Reddit, Discord, WhatsApp ম্যানেজমেন্ট",
    model=get_model("social"),
    db=get_db(),
    tools=other_tools,
    instructions=["পাবলিক পোস্ট করার আগে কনটেন্ট কনফার্ম নাও।", "কোন প্ল্যাটফর্মের key নেই বলো।"],
    markdown=True,
    **MEMORY_KWARGS,
)
