"""
YouTube এজেন্ট — সার্চের জন্য Agno-র নেটিভ YouTubeTools (ফ্রি), আর আপলোড/চ্যানেল
ম্যানেজমেন্টের জন্য PythonTools দিয়ে YouTube Data API v3 কল (Google Cloud key লাগে)।
"""
from agno.agent import Agent
from config import get_model, get_db, has_key, MEMORY_KWARGS
from agno.tools.python import PythonTools

yt_tools = [PythonTools()]

try:
    from agno.tools.youtube import YouTubeTools
    yt_tools.append(YouTubeTools())  # ভিডিও সার্চ/মেটাডেটা — ফ্রি
except Exception:
    pass

yt_upload_ready = has_key("YOUTUBE_API_KEY")

youtube_agent = Agent(
    name="YouTube Agent",
    role="ভিডিও সার্চ (ফ্রি), চ্যানেল/ভিডিও আপলোড ও ম্যানেজমেন্ট (key লাগবে)",
    model=get_model("social"),
    db=get_db(),
    tools=yt_tools,
    instructions=[
        "সার্চের জন্য YouTubeTools ব্যবহার করো।",
        "আপলোড/মেটাডেটা-এডিট দরকার হলে YouTube Data API v3 YOUTUBE_API_KEY (ও OAuth token) দিয়ে Python-এ কল করো।",
        "key না থাকলে জানাও, সিস্টেম থামিয়ো না।",
    ],
    markdown=True,
    **MEMORY_KWARGS,
)

if not yt_upload_ready:
    print("⚠️  YouTube Agent আপলোড করতে পারবে না — .env-এ YOUTUBE_API_KEY বসাও (Google Cloud Console থেকে)।")
