from agno.agent import Agent
from config import get_model, get_db, has_key, MEMORY_KWARGS

tg_tools = []
if has_key("TELEGRAM_TOKEN"):
    from agno.tools.telegram import TelegramTools
    tg_tools.append(TelegramTools())

telegram_agent = Agent(
    name="Telegram Agent",
    role="Telegram চ্যানেল/বট/গ্রুপে মেসেজ পাঠায়, ব্রডকাস্ট করে",
    model=get_model("social"),
    db=get_db(),
    tools=tg_tools,
    instructions=["মেসেজ পাঠানোর আগে কনফার্ম নাও (গুরুত্বপূর্ণ/মাস মেসেজের ক্ষেত্রে)।"],
    markdown=True,
    **MEMORY_KWARGS,
)

if not tg_tools:
    print("⚠️  Telegram Agent-এর জন্য .env-এ TELEGRAM_TOKEN বসাও (BotFather থেকে ফ্রি পাওয়া যায়)।")
