"""
snapshot.py
===========
রিস্কি সিস্টেম-অ্যাকশনের (প্যাকেজ ইনস্টল/রিমুভ, সার্ভিস কন্ট্রোল, ইত্যাদি) আগে
একটা রিস্টোর-পয়েন্ট তৈরির সুবিধা — Timeshift ব্যবহার করে (Debian-based সিস্টেমে
সবচেয়ে পরিচিত ও নির্ভরযোগ্য টুল, rsync মোডে যেকোনো ফাইলসিস্টেমেই কাজ করে,
btrfs/ext4 কী তা নিয়ে ভাবতে হয় না)।

সততার সাথে সীমাবদ্ধতা:
- Timeshift-এর স্ন্যাপশট **পুরো সিস্টেম রিস্টোর** করে (রিবুট করে) — এটা কোনো
  ফাইন-গ্রেইনড "শুধু এই একটা ফাইল/অ্যাকশন undo করো" মেকানিজম না। ভারী
  অ্যাকশনের (প্যাকেজ ইনস্টল, সার্ভিস কনফিগ বদলানো) আগে-পরের একটা নিরাপত্তা-জাল
  হিসেবে ভাবা ভালো, প্রতি মাউস-ক্লিকের জন্য না (তাহলে ডিস্ক দ্রুত ভরে যাবে)।
- root/sudo লাগে — privilege.py-র build_privileged_command ব্যবহার করে, তাই
  passwordless sudo সেট না থাকলে স্পষ্ট এরর দেবে, চুপচাপ ব্যর্থ হবে না।
- Timeshift ইনস্টল করা না থাকলে (বা প্রথমবার কনফিগার করা না থাকলে — যেমন কোন
  ডিস্ক/পার্টিশনে স্ন্যাপশট রাখবে) এই মডিউল সেটা স্পষ্টভাবে জানিয়ে দেবে এবং
  guardrail সিস্টেমকে **ব্লক করবে না** — স্ন্যাপশট ছাড়াই কাজ এগিয়ে যাবে, শুধু
  একটা সতর্কতা যোগ হবে (approval-flow-এর অংশ হিসেবে ইউজার সেটা দেখতে পাবে)।
"""

import json
import logging
import shutil
import subprocess

from privilege import build_privileged_command, PrivilegeError

logger = logging.getLogger("snapshot")


def timeshift_available() -> bool:
    return shutil.which("timeshift") is not None


def timeshift_configured() -> bool:
    """Timeshift প্রথমবার কনফিগার করা (backup device সেট করা) না থাকলে
    --create কমান্ড ব্যর্থ হবে। এটা আগেভাগে চেক করে স্পষ্ট মেসেজ দেওয়ার জন্য।"""
    try:
        result = subprocess.run(
            ["timeshift", "--list"], capture_output=True, text=True, timeout=15,
        )
        # কনফিগার করা না থাকলে stderr/stdout-এ এই ধরনের বার্তা থাকে
        combined = (result.stdout + result.stderr).lower()
        return "backup device" not in combined and "not selected" not in combined
    except Exception:
        return False


def create_snapshot(reason: str) -> dict:
    """একটা Timeshift স্ন্যাপশট তৈরি করে। ব্যর্থ হলে exception না ছুঁড়ে একটা
    স্পষ্ট dict রিটার্ন করে (best-effort — ক্যালিং কোড এটা দিয়ে ব্লক করবে না)।

    Args:
        reason: কেন এই স্ন্যাপশট নেওয়া হচ্ছে (Timeshift কমেন্টে সেভ হয়)
    """
    if not timeshift_available():
        return {"status": "unavailable",
                "message": "Timeshift ইনস্টল করা নেই — 'sudo apt install timeshift' করলে "
                            "এই সেফটি-নেট চালু হবে। এখন স্ন্যাপশট ছাড়াই এগোনো হচ্ছে।"}
    if not timeshift_configured():
        return {"status": "unconfigured",
                "message": "Timeshift ইনস্টল আছে কিন্তু প্রথমবার কনফিগার করা হয়নি "
                            "(কোন ডিস্কে স্ন্যাপশট রাখবে সেট করা নেই) — GUI/CLI-তে একবার "
                            "'sudo timeshift --setup' চালাও। এখন স্ন্যাপশট ছাড়াই এগোনো হচ্ছে।"}

    comment = f"agno-auto: {reason}"[:250]
    try:
        argv = build_privileged_command(["timeshift", "--create", "--comments", comment, "--tags", "D"])
    except PrivilegeError as e:
        return {"status": "error", "message": str(e)}

    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=600)
        if result.returncode == 0:
            logger.info("Snapshot তৈরি হয়েছে: %s", comment)
            return {"status": "created", "comment": comment, "stdout": result.stdout[-1000:]}
        return {"status": "failed", "stdout": result.stdout[-1000:], "stderr": result.stderr[-1000:]}
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": "Timeshift স্ন্যাপশট তৈরি ১০ মিনিটেও শেষ হয়নি (timeout)।"}
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "message": str(e)}


def list_snapshots() -> dict:
    if not timeshift_available():
        return {"status": "unavailable", "snapshots": []}
    try:
        result = subprocess.run(["timeshift", "--list"], capture_output=True, text=True, timeout=15)
        return {"status": "ok", "raw": result.stdout}
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "message": str(e)}


# ---------------------------------------------------------- agent-facing ---

from agno.tools.toolkit import Toolkit


class SnapshotTools(Toolkit):
    """সিস্টেম-লেভেল রিস্কি কাজের আগে/পরে ম্যানুয়ালি রিস্টোর-পয়েন্ট নেওয়ার টুল
    (রিস্কি linux_tools.py অ্যাকশনগুলো ইতিমধ্যেই স্বয়ংক্রিয়ভাবে এটা কল করে —
    এটা এজেন্টকে সরাসরিও অ্যাক্সেস দেয়, যেমন কোনো বড় পরিবর্তনের ঠিক আগে ইউজার
    নিজে থেকে চাইলে)।"""

    def __init__(self, **kwargs):
        super().__init__(name="snapshot_tools", tools=[self.create_restore_point, self.list_restore_points], **kwargs)

    def create_restore_point(self, reason: str) -> str:
        """সিস্টেমের একটা রিস্টোর-পয়েন্ট (Timeshift স্ন্যাপশট) তৈরি করো — কোনো বড়
        পরিবর্তনের আগে নেওয়া ভালো, যাতে সমস্যা হলে সিস্টেম আগের অবস্থায় ফিরিয়ে
        আনা যায় (রিবুট করে, Timeshift GUI/CLI দিয়ে)।

        Args:
            reason: কেন নিচ্ছ (যেমন "nginx ইনস্টলের আগে")
        """
        return json.dumps(create_snapshot(reason), ensure_ascii=False)

    def list_restore_points(self) -> str:
        """বিদ্যমান সব রিস্টোর-পয়েন্ট (Timeshift স্ন্যাপশট) দেখাও।"""
        return json.dumps(list_snapshots(), ensure_ascii=False)
