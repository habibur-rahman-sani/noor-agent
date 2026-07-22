from agno.team.team import Team
from config import get_model, get_db, MEMORY_KWARGS
from agents.facebook_agent import facebook_agent
from agents.tiktok_agent import tiktok_agent
from agents.youtube_agent import youtube_agent
from agents.telegram_agent import telegram_agent
from agents.social_other_agent import social_other_agent

team = Team(
    name="Social Media Team",
    mode="coordinate",
    model=get_model("social"),
    db=get_db(),
    members=[facebook_agent, tiktok_agent, youtube_agent, telegram_agent, social_other_agent],
    instructions=[
        "Facebook/Instagram পোস্ট/অ্যাড/F-commerce -> Facebook Agent।",
        "TikTok কনটেন্ট/অ্যাড -> TikTok Agent।",
        "YouTube সার্চ/আপলোড -> YouTube Agent।",
        "Telegram মেসেজ/ব্রডকাস্ট -> Telegram Agent।",
        "X/Reddit/Discord/WhatsApp -> Other Social Agent।",
        "পাবলিশ/পেইড ক্যাম্পেইনের মতো রিয়েল-ওয়ার্ল্ড ইমপ্যাক্ট আছে এমন অ্যাকশনের আগে ইউজারের কনফার্মেশন নিশ্চিত করো।",
    ],
    markdown=True,
    **MEMORY_KWARGS,
)
