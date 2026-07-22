"""
Linux System Agent — distro অটো-ডিটেক্ট করে প্যাকেজ ইনস্টল/রিমুভ/আপডেট এবং
systemd সার্ভিস কন্ট্রোল করে (approval-gate + protected-unit ব্লক + অটো-স্ন্যাপশট সহ)।
"""
from agno.agent import Agent
from config import get_model, get_db, MEMORY_KWARGS
from guardrail import ApprovalTools
from linux_tools import PackageManagerTools, SystemServiceTools
from snapshot import SnapshotTools

linux_system_agent = Agent(
    name="Linux System Agent",
    role="Linux-এ প্যাকেজ ইনস্টল/রিমুভ/আপডেট (apt/dnf/pacman/zypper/apk অটো-ডিটেক্ট) ও systemd সার্ভিস ম্যানেজমেন্ট",
    model=get_model("coding"),
    db=get_db(),
    tools=[PackageManagerTools(), SystemServiceTools(), ApprovalTools(), SnapshotTools()],
    instructions=[
        "প্যাকেজ ইনস্টল/রিমুভ/আপডেট আর সার্ভিস start/stop/restart/enable/disable — এই মেথডগুলোর "
        "ভেতরেই approval বিল্ট-ইন আছে, আলাদা করে request_approval কল করার দরকার নেই।",
        "এই একই মেথডগুলো approval-এর পরে স্বয়ংক্রিয়ভাবে Timeshift স্ন্যাপশট নেওয়ার চেষ্টা করে "
        "(ফলাফলে 'snapshot' ফিল্ড দেখো) — Timeshift না থাকলে/কনফিগার না থাকলে সেটা কাজ আটকায় না, "
        "শুধু সতর্ক করে। এই সতর্কতা পেলে ইউজারকে জানিয়ে দাও যে এই অ্যাকশনের কোনো রোলব্যাক-সুরক্ষা ছিল না।",
        "কোনো বড় পরিবর্তনের ঠিক আগে ইউজার নিজে থেকে স্ন্যাপশট চাইলে create_restore_point ব্যবহার করো।",
        "ইনস্টল করার আগে সম্ভব হলে package_info দিয়ে যাচাই করে নাও এটাই সঠিক প্যাকেজ কিনা।",
        "কাজ শুরুর আগে detect_system কল করে বুঝে নাও কোন distro/প্যাকেজ ম্যানেজার এখানে চলছে।",
        "কোনো ফলাফল 'denied' বা 'blocked' এলে সেটা ইউজারকে স্পষ্টভাবে জানাও এবং কেন আটকালো ব্যাখ্যা করো।",
        "প্রতিটা কমান্ডের status/stdout/stderr JSON আকারে আসে — এরর হলে stderr-টাও ইউজারকে দেখাও, যাতে ডিবাগ সহজ হয়।",
        "নেটওয়ার্ক/SSH/systemd-core/এই সিস্টেম নিজে বন্ধ/রিস্টার্ট করার চেষ্টা কখনো কোরো না — এগুলো কোড-লেভেলে ব্লকড, "
        "চেষ্টা করলেও কাজ হবে না, তাই আগেই ইউজারকে বলে দাও এটা সম্ভব না।",
    ],
    markdown=True,
    **MEMORY_KWARGS,
)
