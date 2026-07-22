from agno.agent import Agent
from config import get_model, get_db, has_key, MEMORY_KWARGS

comm_tools = []

if has_key("SLACK_TOKEN"):
    from agno.tools.slack import SlackTools
    comm_tools.append(SlackTools())

if has_key("GMAIL_CREDENTIALS_PATH"):
    from agno.tools.gmail import GmailTools
    comm_tools.append(GmailTools())

if has_key("EMAIL_SENDER", "EMAIL_PASSWORD"):
    from agno.tools.email import EmailTools
    import os
    comm_tools.append(EmailTools(sender_email=os.getenv("EMAIL_SENDER"), sender_password=os.getenv("EMAIL_PASSWORD")))

communication_agent = Agent(
    name="Communication Agent",
    role="Slack/Gmail/Email-এর মাধ্যমে মেসেজ পাঠায় ও পড়ে (ব্যক্তিগত/টিম যোগাযোগ)",
    model=get_model("general"),
    db=get_db(),
    tools=comm_tools,
    instructions=[
        "গুরুত্বপূর্ণ মেসেজ পাঠানোর আগে content দেখিয়ে কনফার্ম নাও।",
        "কোনো key না থাকলে ইউজারকে জানাও কোনটা .env-এ দিতে হবে।",
    ],
    markdown=True,
    **MEMORY_KWARGS,
)

if not comm_tools:
    print("⚠️  Communication Agent-এ কোনো টুল সক্রিয় নেই — .env-এ SLACK_TOKEN / GMAIL_CREDENTIALS_PATH / EMAIL_SENDER+EMAIL_PASSWORD বসাও।")
