"""
Facebook / Instagram এজেন্ট
============================
Agno-তে রেডিমেড Facebook/Instagram টুলকিট নেই, তাই এই এজেন্টকে PythonTools দেওয়া
আছে — সে নিজে Facebook/Instagram Graph API-তে requests লাইব্রেরি দিয়ে কল করবে
(পেজ পোস্ট, ক্যাম্পেইন/অ্যাড তৈরি, ক্যাটালগ/F-commerce ম্যানেজমেন্ট, ইনসাইট দেখা ইত্যাদি)।

দরকারি key: FACEBOOK_ACCESS_TOKEN, FACEBOOK_PAGE_ID, FACEBOOK_AD_ACCOUNT_ID
(এগুলো পেতে Meta for Developers-এ অ্যাপ বানিয়ে Business verification করতে হয় —
এটা শুধু .env-এ key বসানোর চেয়ে বেশি কিছু, Meta-র নিজস্ব approval প্রসেস আছে)
"""
from agno.agent import Agent
from config import get_model, get_db, has_key, MEMORY_KWARGS
from tools_free import SEARCH_TOOLS
from guardrail import ApprovalTools, APPROVAL_INSTRUCTION

fb_tools = [t for t in SEARCH_TOOLS if t.name == "duckduckgo_tools"]

from agno.tools.python import PythonTools
fb_tools.append(PythonTools())
fb_tools.append(ApprovalTools())

fb_ready = has_key("FACEBOOK_ACCESS_TOKEN", "FACEBOOK_PAGE_ID")

facebook_agent = Agent(
    name="Facebook Agent",
    role="Facebook/Instagram পেজ ম্যানেজমেন্ট, পোস্টিং, অ্যাড ক্যাম্পেইন, F-commerce/ক্যাটালগ ম্যানেজমেন্ট",
    model=get_model("social"),
    db=get_db(),
    tools=fb_tools,
    instructions=[
        "Facebook Graph API endpoint: https://graph.facebook.com/v21.0/ — "
        "environment variable FACEBOOK_ACCESS_TOKEN আর FACEBOOK_PAGE_ID/FACEBOOK_AD_ACCOUNT_ID ব্যবহার করে "
        "Python-এর requests লাইব্রেরি দিয়ে কল করো।",
        "অ্যাড ক্যাম্পেইন তৈরি/পেমেন্ট-সংক্রান্ত যেকোনো অ্যাকশনের আগে (এটা রিয়েল টাকা খরচ করতে পারে) " + APPROVAL_INSTRUCTION,
        "key না থাকলে/অ্যাক্সেস টোকেন ভুল হলে স্পষ্ট এরর দেখাও এবং কী লাগবে বলো, থেমে থেকো না — অন্য কাজে চলে যাও।",
    ],
    markdown=True,
    **MEMORY_KWARGS,
)

if not fb_ready:
    print("⚠️  Facebook Agent-এর জন্য .env-এ FACEBOOK_ACCESS_TOKEN ও FACEBOOK_PAGE_ID বসাও (Meta for Developers থেকে)।")
