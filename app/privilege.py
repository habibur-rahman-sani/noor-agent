"""
privilege.py
============
Linux root-privilege escalation — নিয়ন্ত্রিত ও অডিটযোগ্য।

এখানে "ALL=(ALL) NOPASSWD: ALL"-এর মতো বিপজ্জনক কিছু করা হয় না। install.sh
ইউজারের স্পষ্ট সম্মতি নিয়ে /etc/sudoers.d/agno-system ফাইলে **শুধু নির্দিষ্ট
বাইনারির জন্য** পাসওয়ার্ডহীন sudo সেট করে (visudo -c দিয়ে সিনট্যাক্স যাচাই করার
পরই, নাহলে ভুল sudoers ফাইল পুরো sudo-ই ভেঙে দিতে পারে — তাই এই চেক বাধ্যতামূলক)।

এই মডিউলের কাজ শুধু: দরকার হলে কমান্ডের সামনে sudo যোগ করা, আর পাসওয়ার্ডহীন
sudo সেট করা না থাকলে **হ্যাং করার বদলে সাথে সাথে স্পষ্ট এরর** দেওয়া।
"""

import os
import shutil
import subprocess


class PrivilegeError(Exception):
    """root প্রিভিলেজ দরকার কিন্তু নিরাপদে পাওয়া গেল না — কল করা কোড এটা ধরে
    ইউজার-ফ্রেন্ডলি মেসেজ দেখাবে, প্রসেস ক্র্যাশ করবে না।"""


def has_root() -> bool:
    return hasattr(os, "geteuid") and os.geteuid() == 0


def has_passwordless_sudo(binary_path: str) -> bool:
    """`sudo -n -l <binary>` — নন-ইন্টারঅ্যাক্টিভ (-n), তাই পাসওয়ার্ড লাগলে
    প্রম্পট না দেখিয়ে সাথে সাথে ব্যর্থ হয়। কখনো হ্যাং করে না।"""
    try:
        result = subprocess.run(
            ["sudo", "-n", "-l", binary_path],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def build_privileged_command(argv: list) -> list:
    """
    root হিসেবে চললে argv অপরিবর্তিত রাখে। না হলে পাসওয়ার্ডহীন sudo সেট
    আছে কিনা চেক করে — থাকলে সামনে ["sudo", "-n"] বসায়, না থাকলে PrivilegeError
    রেইজ করে স্পষ্ট সমাধানসহ।
    """
    if not argv:
        raise ValueError("argv খালি — অন্তত একটা কমান্ড দরকার।")

    if has_root():
        return argv

    binary = shutil.which(argv[0]) or argv[0]
    if has_passwordless_sudo(binary):
        return ["sudo", "-n"] + argv

    user = os.environ.get("USER", "agno")
    raise PrivilegeError(
        f"'{binary}' চালাতে root প্রিভিলেজ দরকার, কিন্তু পাসওয়ার্ডহীন sudo সেট করা নেই। "
        f"সমাধান: প্রজেক্ট ফোল্ডারে গিয়ে 'bash install.sh' আবার চালাও (sudoers.d এন্ট্রি সেট করবে), "
        f"অথবা ম্যানুয়ালি 'sudo visudo -f /etc/sudoers.d/agno-system' দিয়ে "
        f"'{user} ALL=(root) NOPASSWD: {binary}' লাইন যোগ করো।"
    )
