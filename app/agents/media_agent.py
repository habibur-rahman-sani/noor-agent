from agno.agent import Agent
from config import get_model, get_db, has_key, MEMORY_KWARGS
from tools_free import MISC_TOOLS

media_tools = [t for t in MISC_TOOLS if t.name == "moviepy_video_tools"]

if has_key("OPENAI_API_KEY"):
    from agno.tools.models.openai import OpenAITools
    media_tools.append(OpenAITools())

if has_key("FAL_KEY"):
    from agno.tools.fal import FalTools
    media_tools.append(FalTools())

if has_key("ELEVEN_LABS_API_KEY"):
    from agno.tools.eleven_labs import ElevenLabsTools
    media_tools.append(ElevenLabsTools())

media_agent = Agent(
    name="Media Agent",
    role="ইমেজ/অডিও/ভিডিও জেনারেট ও এডিট করে",
    model=get_model("creative"),
    db=get_db(),
    tools=media_tools,
    instructions=["জেনারেশনের আগে স্টাইল/ফরম্যাট নিশ্চিত করো।", "কোন প্রোভাইডারের key নেই বলো।"],
    markdown=True,
    **MEMORY_KWARGS,
)
