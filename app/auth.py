"""
auth.py — ওয়েব UI/API-র জন্য HTTP Basic Auth
=================================================
আগে server.py --host 0.0.0.0-এ কোনো লগইন ছাড়াই চলত — মানে একই নেটওয়ার্কে
থাকা যে কেউ ব্রাউজারে IP:8000 দিয়ে ঢুকে সরাসরি এজেন্টের সাথে কথা বলতে পারত
(এজেন্টের সিস্টেম-লেভেল কন্ট্রোলের ক্ষমতা থাকায় এটা ঝুঁকিপূর্ণ ছিল)। এখন
সব রুট (health-check বাদে) HTTP Basic Auth দিয়ে সুরক্ষিত।

পাসওয়ার্ড কোথা থেকে আসে (অগ্রাধিকার অনুযায়ী):
  ১. .env-এ AGNO_UI_PASSWORD সেট থাকলে সেটাই ব্যবহার হয়।
  ২. না থাকলে (যেমন 'bash install.sh' দিয়ে সাধারণ ইনস্টলে) একটা র‍্যান্ডম
     পাসওয়ার্ড অটো-জেনারেট করে .env-এ সেভ করে দেয় এবং সার্ভার লগে স্পষ্টভাবে
     দেখায় (journalctl -u agno-system দিয়ে দেখা যাবে)।
  (ISO বিল্ডে অবশ্য 0200-agno-venv-setup.hook.chroot বিল্ড-টাইমেই একটা
  পাসওয়ার্ড জেনারেট করে .env + ডেস্কটপের README-FIRST.txt-এ লিখে রাখে,
  তাই ISO থেকে বুট করা সিস্টেমে এই ফলব্যাক সাধারণত লাগবেই না।)
"""
import os
import secrets
import logging
from pathlib import Path

logger = logging.getLogger("agno-auth")

ENV_PATH = Path(__file__).parent / ".env"


def _persist_password_to_env(password: str) -> None:
    """.env ফাইলে AGNO_UI_PASSWORD লাইন যোগ/আপডেট করে।"""
    if ENV_PATH.exists():
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
        found = False
        for i, line in enumerate(lines):
            if line.startswith("AGNO_UI_PASSWORD="):
                lines[i] = f"AGNO_UI_PASSWORD={password}"
                found = True
                break
        if not found:
            lines.append(f"AGNO_UI_PASSWORD={password}")
        ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        ENV_PATH.write_text(f"AGNO_UI_PASSWORD={password}\n", encoding="utf-8")


def get_ui_credentials() -> tuple[str, str]:
    """(username, password) রিটার্ন করে — .env-এ পাসওয়ার্ড না থাকলে অটো-জেনারেট ও সেভ করে।"""
    username = os.getenv("AGNO_UI_USERNAME", "agno").strip() or "agno"
    password = os.getenv("AGNO_UI_PASSWORD", "").strip()
    if not password:
        password = secrets.token_urlsafe(12)
        os.environ["AGNO_UI_PASSWORD"] = password
        try:
            _persist_password_to_env(password)
            save_note = "(.env ফাইলে সেভ হয়ে গেছে)"
        except Exception:
            logger.exception("AGNO_UI_PASSWORD .env-এ সেভ করা যায়নি।")
            save_note = "(⚠️ .env-এ সেভ করা যায়নি — সার্ভার রিস্টার্ট করলে বদলে যাবে, ম্যানুয়ালি .env-এ বসিয়ে নাও)"
        logger.warning(
            "=" * 70 + "\n"
            "🔐 কোনো AGNO_UI_PASSWORD সেট করা ছিল না — একটা নতুন পাসওয়ার্ড অটো-জেনারেট করা হয়েছে %s\n"
            "   ইউজারনেম: %s\n"
            "   পাসওয়ার্ড: %s\n"
            "   ব্রাউজারে http://<এই-মেশিনের-IP>:8000 খুললে এই ইউজারনেম/পাসওয়ার্ড চাইবে।\n"
            "   বদলাতে চাইলে .env-এ AGNO_UI_PASSWORD এডিট করে সার্ভিস রিস্টার্ট করো।\n"
            + "=" * 70,
            save_note, username, password,
        )
    return username, password
