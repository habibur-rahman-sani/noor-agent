"""
registry.py
===========
teams/ ফোল্ডারের প্রতিটা .py ফাইল স্ক্যান করে, যেই ফাইলে `team = Team(...)`
ভ্যারিয়েবল পাওয়া যায় সেটা অটোমেটিক লোড করে নেয়।

মানে: ভবিষ্যতে নতুন টিম যোগ করতে চাইলে শুধু teams/ ফোল্ডারে একটা নতুন .py
ফাইল বানাও, তাতে `team = Team(...)` ডিফাইন করো — supervisor.py-তে কিছু
বদলাতে হবে না, এটা নিজে থেকেই ধরে নেবে।

ফল্ট-আইসোলেশন: প্রতিটা team-মডিউল আলাদাভাবে try/except দিয়ে ইম্পোর্ট করা হয়।
একটা team-এর কোনো সমস্যা থাকলে (মিসিং dependency, নিজস্ব bug, মিসিং env var
ইত্যাদি) শুধু সেই team বাদ পড়ে ও একটা স্পষ্ট warning লগ হয় — বাকি সব team ঠিকমতো
লোড হয় এবং সার্ভার স্বাভাবিকভাবে বুট হয়। আগে একটা team-এর import ব্যর্থ হলে পুরো
`load_all_teams()` exception ছুঁড়ে দিত, ফলে পুরো সুপারভাইজার/সার্ভারই বুট হতে
ব্যর্থ হতো — এটাই সেই সমস্যার ফিক্স।
"""
import importlib
import logging
import pkgutil
import pathlib

logger = logging.getLogger("teams.registry")


def load_all_teams():
    teams = []
    failed = []
    package_dir = pathlib.Path(__file__).parent
    for _, module_name, _ in sorted(pkgutil.iter_modules([str(package_dir)])):
        if module_name in ("registry",):
            continue
        try:
            module = importlib.import_module(f"teams.{module_name}")
        except Exception:
            logger.exception(
                "'%s' টিম লোড করা যায়নি — এটা বাদ দিয়ে বাকি সিস্টেম চালু থাকবে। "
                "সম্ভাব্য কারণ: মিসিং API key/env var, মিসিং pip dependency, বা এই "
                "মডিউলের/এর এজেন্টের নিজস্ব bug। সমাধানের জন্য পুরো traceback উপরে দেখো।",
                module_name,
            )
            failed.append(module_name)
            continue
        if hasattr(module, "team"):
            teams.append(module.team)
        else:
            logger.warning(
                "'%s' মডিউলে কোনো 'team' ভ্যারিয়েবল পাওয়া যায়নি — স্কিপ করা হলো।",
                module_name,
            )

    if not teams:
        raise RuntimeError(
            "কোনো টিমই লোড করা যায়নি (সবগুলো ব্যর্থ হয়েছে) — সার্ভার চালানোর কোনো "
            "মানে নেই। উপরের লগে প্রতিটা টিমের ব্যর্থতার কারণ দেখো।"
        )
    if failed:
        logger.warning(
            "%d/%d টিম লোড হয়নি (%s) — এই টিমগুলো ছাড়া সার্ভার চালু হচ্ছে।",
            len(failed), len(failed) + len(teams), ", ".join(failed),
        )
    return teams
