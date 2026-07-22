"""
Media Generation এজেন্ট — ছবি (ও ভবিষ্যতে ভিডিও) তৈরি করা।
OPENAI_API_KEY থাকলে OpenAI Images API ব্যবহার হয় (পেইড, কিন্তু সস্তা)।
FAL_KEY থাকলে fal.ai-এর ওপেন-মডেল ইমেজ জেনারেশনও যোগ করা যায় (এখানে placeholder
হিসেবে রাখা হলো, has_key দিয়ে গার্ড করা — চাইলে নির্দিষ্ট fal মডেল যোগ করে দেব)।
key না থাকলে agent স্পষ্টভাবে বলে দেবে কোন key লাগবে।
"""
from agno.agent import Agent
from agno.tools.toolkit import Toolkit
from config import get_model, get_db, has_key, MEMORY_KWARGS

media_gen_tools = []

if has_key("OPENAI_API_KEY"):
    class OpenAIImageTools(Toolkit):
        def __init__(self, **kwargs):
            super().__init__(name="openai_image_tools", tools=[self.generate_image], **kwargs)

        def generate_image(self, prompt: str, save_path: str = "generated_image.png", size: str = "1024x1024") -> str:
            """OpenAI Images API দিয়ে prompt থেকে ছবি বানিয়ে ফাইলে সেভ করে।

            Args:
                prompt: ছবির বর্ণনা
                save_path: কোথায় সেভ হবে
                size: "1024x1024" | "1024x1792" | "1792x1024"
            """
            try:
                import base64
                from openai import OpenAI

                client = OpenAI()
                result = client.images.generate(model="gpt-image-1", prompt=prompt, size=size)
                image_b64 = result.data[0].b64_json
                with open(save_path, "wb") as f:
                    f.write(base64.b64decode(image_b64))
                return f"ছবি তৈরি হয়েছে: {save_path}"
            except Exception as e:  # noqa: BLE001
                return f"ছবি তৈরি ব্যর্থ হয়েছে: {e}"

    media_gen_tools.append(OpenAIImageTools())

media_gen_agent = Agent(
    name="Media Generation Agent",
    role="prompt থেকে ছবি (ও ভবিষ্যতে ভিডিও) তৈরি করা",
    model=get_model("creative"),
    db=get_db(),
    tools=media_gen_tools,
    instructions=[
        "কোনো জেনারেশন টুল লোড না হলে (OPENAI_API_KEY/FAL_KEY নেই) সেটা স্পষ্টভাবে বলো এবং "
        "কোন key .env-এ বসালে কাজ করবে সেটা জানাও।",
        "কপিরাইটেড চরিত্র/লোগো/বাস্তব মানুষের ছবি তৈরির অনুরোধ এলে বিকল্প (মৌলিক/জেনেরিক ডিজাইন) প্রস্তাব করো।",
    ],
    markdown=True,
    **MEMORY_KWARGS,
)
