"""
Scheduler এজেন্ট — "proactive layer"। এই এজেন্টের কারণেই সিস্টেম শুধু জিজ্ঞেস
করলে উত্তর দেওয়া না, নিজে থেকে নির্দিষ্ট সময়ে/পুনরাবৃত্তিতে কাজ করতে পারবে
(রিমাইন্ডার, রুটিন চেক-আপ, ভবিষ্যতে কোনো কাজ আবার করা)।
"""
from agno.agent import Agent
from config import get_model, get_db, MEMORY_KWARGS
from scheduler import SchedulerTools

scheduler_agent = Agent(
    name="Scheduler Agent",
    role="ভবিষ্যতের জন্য এক-বারের বা পুনরাবৃত্ত কাজ শিডিউল করা, তালিকা দেখা, বাতিল করা — proactive/রিমাইন্ডার সিস্টেম",
    model=get_model("general"),
    db=get_db(),
    tools=[SchedulerTools()],
    instructions=[
        "সময়সীমা সবসময় UTC-তে হিসাব করে ব্যবহারকারীর স্থানীয় সময় থেকে কনভার্ট করো "
        "(ইউজারের টাইমজোন স্পষ্ট না হলে জিজ্ঞেস করো)।",
        "পুনরাবৃত্ত কাজের জন্য standard ৫-ফিল্ড cron এক্সপ্রেশন ব্যবহার করো।",
        "শিডিউল করা কাজ ফায়ার হলে সেটা সরাসরি Supervisor-কে prompt আকারে পাঠানো হবে "
        "এবং ফলাফল ডেস্কটপ নোটিফিকেশন + ডাটাবেসে লগ হবে — এটা ইউজারকে জানিয়ে রাখো।",
        "কোনো শিডিউল তৈরি/বাতিলের আগে সংক্ষেপে নিশ্চিত করে নাও ঠিক কী/কখন চাওয়া হচ্ছে।",
    ],
    markdown=True,
    **MEMORY_KWARGS,
)
