"""
notification_core.py
=====================
Linux ডেস্কটপ নোটিফিকেশন — শুধু `notify-send` (libnotify) ব্যবহার করে, যেটা এই
ISO-তে (Openbox + লাইটওয়েট ডেস্কটপ) ডিফল্টভাবে পাওয়া যাবে (`libnotify-bin`
প্যাকেজ-লিস্টে যোগ করা আছে)। `plyer` ইনস্টল থাকলে সেটাও চেষ্টা করা হয় (একই
কোড অন্য কোনো পরিবেশে চালালেও কাজ করার সম্ভাবনা বাড়ায়), কিন্তু মূল নির্ভরতা
notify-send-এর উপর।
"""

import logging
import shutil
import subprocess

logger = logging.getLogger("agno-notify")


def send_desktop_notification(title: str, message: str) -> bool:
    # ১) plyer — ইনস্টল থাকলে সবচেয়ে সহজ পথ
    try:
        from plyer import notification as plyer_notification
        plyer_notification.notify(title=title, message=message, timeout=8)
        return True
    except Exception:
        pass

    # ২) notify-send (libnotify) — এই Linux ISO-তে ডিফল্টভাবে ইনস্টল করা থাকে
    if shutil.which("notify-send"):
        try:
            subprocess.run(["notify-send", title, message], check=False)
            return True
        except Exception:
            pass

    logger.warning(
        "কোনো নোটিফিকেশন চ্যানেল পাওয়া যায়নি (notify-send নেই) — শুধু লগ করা হলো: %s / %s",
        title, message,
    )
    return False
