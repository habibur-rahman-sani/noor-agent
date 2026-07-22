"""
TikTok এজেন্ট — TikTok-এরও কোনো নেটিভ Agno টুলকিট নেই, তাই PythonTools দিয়ে
TikTok Business API (Content Posting API / Marketing API) কল করবে।
দরকারি key: TIKTOK_ACCESS_TOKEN, TIKTOK_ADVERTISER_ID
"""
from agno.agent import Agent
from config import get_model, get_db, has_key, MEMORY_KWARGS
from agno.tools.python import PythonTools

tiktok_ready = has_key("TIKTOK_ACCESS_TOKEN")

tiktok_agent = Agent(
    name="TikTok Agent",
    role="TikTok কনটেন্ট পোস্টিং, অ্যাড ক্যাম্পেইন, পারফরম্যান্স ইনসাইট",
    model=get_model("social"),
    db=get_db(),
    tools=[PythonTools()],
    instructions=[
        "TikTok for Business API (https://business-api.tiktok.com/) TIKTOK_ACCESS_TOKEN দিয়ে কল করো।",
        "পেইড ক্যাম্পেইন তৈরির আগে ইউজারকে কনফার্ম নাও।",
        "key না থাকলে জানাও, কিন্তু সিস্টেম থেমে থেকো না।",
    ],
    markdown=True,
    **MEMORY_KWARGS,
)

if not tiktok_ready:
    print("⚠️  TikTok Agent-এর জন্য .env-এ TIKTOK_ACCESS_TOKEN বসাও (TikTok for Business থেকে)।")
