"""
IoT/Smart-home এজেন্ট — Home Assistant-এর REST API দিয়ে স্মার্ট ডিভাইস
(লাইট, প্লাগ, থার্মোস্ট্যাট ইত্যাদি) নিয়ন্ত্রণ। Home Assistant একটা ওপেন-সোর্স
হাব যেটা প্রায় সব ব্র্যান্ডের স্মার্ট ডিভাইস সাপোর্ট করে, তাই সরাসরি প্রতিটা
ব্র্যান্ডের API আলাদাভাবে ইন্টিগ্রেট না করে HA-কেই একমাত্র integration পয়েন্ট
রাখা হয়েছে (না থাকলে ইউজারকে ইনস্টল করতে বলে)।

.env-এ HOME_ASSISTANT_URL (যেমন http://homeassistant.local:8123) আর
HOME_ASSISTANT_TOKEN (Long-Lived Access Token, HA প্রোফাইল সেটিংস থেকে) লাগবে।
"""
from agno.agent import Agent
from agno.tools.toolkit import Toolkit
from config import get_model, get_db, has_key, MEMORY_KWARGS
from guardrail import ApprovalTools, APPROVAL_INSTRUCTION

iot_tools = []

if has_key("HOME_ASSISTANT_URL", "HOME_ASSISTANT_TOKEN"):
    import os
    import requests

    class HomeAssistantTools(Toolkit):
        def __init__(self, **kwargs):
            self.base_url = os.environ["HOME_ASSISTANT_URL"].rstrip("/")
            self.headers = {
                "Authorization": f"Bearer {os.environ['HOME_ASSISTANT_TOKEN']}",
                "Content-Type": "application/json",
            }
            super().__init__(name="home_assistant_tools", tools=[self.list_devices, self.call_service], **kwargs)

        def list_devices(self) -> str:
            """Home Assistant-এ যত ডিভাইস/এনটিটি আছে ও তাদের বর্তমান অবস্থা দেখাও।"""
            try:
                resp = requests.get(f"{self.base_url}/api/states", headers=self.headers, timeout=10)
                resp.raise_for_status()
                states = resp.json()
            except Exception as e:  # noqa: BLE001
                return f"Home Assistant-এর সাথে কানেক্ট করা যায়নি: {e}"
            lines = [f"{s['entity_id']}: {s['state']}" for s in states[:100]]
            return "\n".join(lines)

        def call_service(self, domain: str, service: str, entity_id: str) -> str:
            """একটা Home Assistant service কল করো (যেমন লাইট অন/অফ করা)।

            Args:
                domain: যেমন "light", "switch", "climate"
                service: যেমন "turn_on", "turn_off", "toggle"
                entity_id: যেমন "light.living_room"
            """
            try:
                resp = requests.post(
                    f"{self.base_url}/api/services/{domain}/{service}",
                    headers=self.headers, json={"entity_id": entity_id}, timeout=10,
                )
                resp.raise_for_status()
            except Exception as e:  # noqa: BLE001
                return f"সার্ভিস কল ব্যর্থ হয়েছে: {e}"
            return f"'{domain}.{service}' চালানো হয়েছে '{entity_id}'-এর জন্য।"

    iot_tools.append(HomeAssistantTools())

iot_tools.append(ApprovalTools())

iot_agent = Agent(
    name="IoT Agent",
    role="Home Assistant-এর মাধ্যমে স্মার্ট হোম ডিভাইস (লাইট/প্লাগ/থার্মোস্ট্যাট ইত্যাদি) নিয়ন্ত্রণ",
    model=get_model("general"),
    db=get_db(),
    tools=iot_tools,
    instructions=[
        "Home Assistant setup না থাকলে (HOME_ASSISTANT_URL/TOKEN) সেটা স্পষ্টভাবে বলো — "
        "ইনস্টল করতে https://www.home-assistant.io/installation/ দেখতে বলো।",
        "ডিভাইস অন/অফ করার মতো ফিজিক্যাল-world অ্যাকশনের আগে " + APPROVAL_INSTRUCTION,
    ],
    markdown=True,
    **MEMORY_KWARGS,
)
