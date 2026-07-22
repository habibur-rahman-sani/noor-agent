"""
Notification এজেন্ট — যেকোনো টিমের আউটপুট বা সতর্কতা ইউজারকে সঠিক চ্যানেলে
পৌঁছানো (এখন: ডেস্কটপ নোটিফিকেশন; .env-এ key দিলে ভবিষ্যতে SMS/Slack/Telegram-ও
যোগ করা যায়, যেহেতু ওই টুল communication_agent-এ আছে)।
"""
from agno.agent import Agent
from agno.tools.toolkit import Toolkit
from config import get_model, get_db, MEMORY_KWARGS
from notification_core import send_desktop_notification


class NotificationTools(Toolkit):
    def __init__(self, **kwargs):
        super().__init__(name="notification_tools", tools=[self.notify], **kwargs)

    def notify(self, title: str, message: str) -> str:
        """Linux ডেস্কটপে একটা নোটিফিকেশন পাঠাও (notify-send/libnotify দিয়ে)।

        Args:
            title: নোটিফিকেশনের শিরোনাম
            message: মূল বার্তা
        """
        ok = send_desktop_notification(title, message)
        return "নোটিফিকেশন পাঠানো হয়েছে।" if ok else "কোনো নোটিফিকেশন চ্যানেল পাওয়া যায়নি এই ডিভাইসে।"


notification_agent = Agent(
    name="Notification Agent",
    role="Linux ডেস্কটপে নোটিফিকেশন পাঠানো — জরুরি তথ্য/reminder ইউজারের নজরে আনা",
    model=get_model("general"),
    db=get_db(),
    tools=[NotificationTools()],
    instructions=[
        "গুরুত্বপূর্ণ/সময়-সংবেদনশীল তথ্যের জন্যই নোটিফিকেশন ব্যবহার করো, তুচ্ছ প্রতিটা মেসেজের জন্য না।",
        "চ্যানেল পাওয়া না গেলে ইউজারকে জানাও (যেমন Linux-এ libnotify/notify-send ইনস্টল করতে হতে পারে)।",
    ],
    markdown=True,
    **MEMORY_KWARGS,
)
