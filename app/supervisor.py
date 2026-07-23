"""
supervisor.py
=============
টপ-লেভেল সুপারভাইজার। teams/registry.py দিয়ে teams/ ফোল্ডারের সব Team
অটোমেটিক লোড হয় — নতুন Team যোগ করতে চাইলে শুধু teams/ ফোল্ডারে ফাইল বানাও,
এখানে কিছু বদলাতে হবে না।

নোট (গুরুত্বপূর্ণ): supervisor অবজেক্টটা এখন **lazy** — মডিউল import হওয়ার সময়
যদি OPENROUTER_API_KEY না থাকে (বা মডেল তৈরি করতে ব্যর্থ হয়), তবুও import
ক্র্যাশ করবে না; শুধু supervisor=None থাকবে। ফলে key ছাড়াও সার্ভার চালু হয় ও
ব্রাউজারে সেটিংস পেজ খুলে key বসানো যায় (টার্মিনাল ছাড়াই)। key বসানোর পর
rebuild_supervisor() ডাকলে পুরো সিস্টেম চালু হয়ে যায়।
"""
import logging

from agno.team.team import Team
from config import get_model, get_db, MEMORY_KWARGS
from teams.registry import load_all_teams
from memory_core import MemoryTools

logger = logging.getLogger("supervisor")

_INSTRUCTIONS = [
    "তুমি একটা জেনারেল-পারপাস AI সিস্টেমের সুপারভাইজার — ইউজার যা যা করতে চায়, সঠিক টিমের কাছে পাঠাও।",
    "কাজ একাধিক ডোমেইনে পড়লে একাধিক Team ব্যবহার করে ফলাফল একত্র করো।",
    "কোনো কাজ করা সম্ভব না হলে (key/টুল না থাকায়) কোন Team-এ কী লাগবে স্পষ্টভাবে বলো, "
    "কিন্তু বাকি কাজ চালিয়ে যাও — একটা অংশ আটকে গেলে পুরো উত্তর আটকে দিও না।",
    "ঝুঁকিপূর্ণ/অপরিবর্তনীয় কাজে সংশ্লিষ্ট Team নিজেই মানুষের approval চাইবে (guardrail.py) — "
    "এটা যেন এড়িয়ে যাওয়া না হয় সেটা মাথায় রাখো।",
    "ভবিষ্যতে/পুনরাবৃত্তিতে কিছু করাতে চাইলে Scheduler Team ব্যবহার করো।",
    "লিনাক্স প্যাকেজ ইনস্টল/রিমুভ/আপডেট, বা systemd সার্ভিস (nginx/docker ইত্যাদি) start/stop/enable/disable "
    "-> সবসময় Linux System Team-কে দাও, PC Team-এর raw শেল কমান্ড দিয়ে না — Linux System Team-এর "
    "distro-অটো-ডিটেক্ট আর protected-unit সুরক্ষা আছে, যেটা raw শেলে নেই।",
    "ইউজার স্পষ্টভাবে কিছু 'মনে রাখতে' বললে save_important_note ব্যবহার করো। বর্তমান কথোপকথনের "
    "সাম্প্রতিক ইতিহাসে (num_history_runs=10) নেই এমন পুরনো প্রসঙ্গ/সিদ্ধান্ত দরকার হলে "
    "recall_past_context(কীওয়ার্ড) দিয়ে আগের সংক্ষিপ্ত সারাংশ থেকে খুঁজে দেখো — কিছু না পেলে সেটা "
    "স্পষ্টভাবে বলো, অনুমান করে বানিয়ে বোলো না।",
]

supervisor = None
build_error: str | None = None


def build_supervisor():
    """teams সহ পুরো supervisor Team তৈরি করে — key/নেট না থাকলে exception ছুঁড়বে।"""
    return Team(
        name="Supervisor",
        mode="coordinate",
        model=get_model("general"),
        db=get_db(),
        members=load_all_teams(),
        tools=[MemoryTools()],
        instructions=_INSTRUCTIONS,
        markdown=True,
        **MEMORY_KWARGS,
    )


def get_supervisor():
    """তৈরি না থাকলে তৈরি করে ফেরত দেয় (key দরকার — না থাকলে exception)।"""
    global supervisor, build_error
    if supervisor is None:
        supervisor = build_supervisor()
        build_error = None
    return supervisor


def rebuild_supervisor():
    """key বদলানোর/বসানোর পর ডাকো — নতুন করে সব team সহ তৈরি করে।"""
    global supervisor, build_error
    supervisor = build_supervisor()
    build_error = None
    return supervisor


def supervisor_ready() -> bool:
    return supervisor is not None


# import-এর সময় eager build করার চেষ্টা — সফল হলে আগের মতোই আচরণ; ব্যর্থ হলে
# (key নেই) সার্ভার তবু চালু হবে, ইউজার সেটিংস পেজ থেকে key দেবে।
try:
    supervisor = build_supervisor()
except Exception as e:  # noqa: BLE001
    build_error = str(e)
    supervisor = None
    logger.warning("Supervisor এখনো চালু হয়নি (সম্ভবত OPENROUTER_API_KEY নেই): %s", e)


if __name__ == "__main__":
    if supervisor is None:
        print("Supervisor চালু হয়নি:", build_error)
    else:
        print("লোড হওয়া টিম:", [t.name for t in supervisor.members])
