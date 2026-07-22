"""
guardrail.py
============
ঝুঁকিপূর্ণ action-এর আগে মানুষের অনুমোদন (approval) নেওয়ার সিস্টেম।
এটাই AI OS-এর "safety layer" — যত বেশি এজেন্ট বাস্তব সিস্টেমে অ্যাকশন
নেওয়া শুরু করবে, এই layer ততই জরুরি হয়ে উঠবে।

কাজ করে এভাবে:
1. এজেন্ট ঝুঁকিপূর্ণ কাজের আগে (ফাইল ডিলিট, মেসেজ পাঠানো, পারচেজ, নতুন কোড
   ফাইল লেখা ইত্যাদি) `ApprovalTools.request_approval(...)` টুল কল করে।
2. এটা একটা pending approval তৈরি করে (in-memory threading.Event দিয়ে ব্লক
   করে + MongoDB-তে audit-এর জন্য রেকর্ড রাখে)।
3. server.py-র REST এন্ডপয়েন্ট (`/api/approvals`) দিয়ে UI pending approval
   গুলো দেখতে ও approve/deny করতে পারে।
4. ইউজার approve/deny করলে সংশ্লিষ্ট Event সেট হয়ে যায়, `request_approval`
   আনব্লক হয়ে ফলাফল রিটার্ন করে — এজেন্ট তখনই বুঝে যায় এগোবে নাকি থামবে।
5. টাইমআউট (ডিফল্ট ৫ মিনিট) পার হলে auto-deny হয়, যাতে এজেন্ট অনির্দিষ্টকালের
   জন্য আটকে না থাকে।

নোট: এটা single-process in-memory ব্লকিং ব্যবহার করে বলে multi-worker/multi-process
ডিপ্লয়মেন্টে (একাধিক uvicorn worker) কাজ করবে না — সেক্ষেত্রে Redis-ভিত্তিক
broker-এ আপগ্রেড করা লাগবে (README-তে নোট আছে)। ডিফল্ট সার্ভিস টেমপ্লেট single
uvicorn worker-এ চলে (--workers ফ্ল্যাগ নেই), তাই এই মুহূর্তে এটা সমস্যা না।

⚠️ event-loop সেফটি: `threading.Event.wait(timeout=300)` পাঁচ মিনিট পর্যন্ত ব্লক
করতে পারে। যদি এটা সরাসরি (thread pool ছাড়া) asyncio event loop-এ কল হয়, তাহলে
ওই সময় পুরো সার্ভার (সব ইউজার/সেশন) ফ্রিজ হয়ে যাবে। এটা এড়াতে
`request_approval`/`ApprovalTools.request_approval` async করে ভেতরে
`asyncio.to_thread` দিয়ে ব্লকিং wait-টা আলাদা থ্রেডে সরানো হয়েছে — agno যদি sync
টুলও নিজে থ্রেড-পুলে চালায় তাহলেও এটা ক্ষতিকর না, শুধু নিশ্চিত করে যে event loop
কখনোই ব্লক হবে না।
"""

import asyncio
import os
import threading
import uuid
from datetime import datetime, timezone

from agno.tools.toolkit import Toolkit

APPROVAL_TIMEOUT_SECONDS = int(os.getenv("APPROVAL_TIMEOUT_SECONDS", "300"))

_pending: dict[str, dict] = {}
_lock = threading.Lock()


def _raw_db():
    """server.py/scheduler.py-র মতোই সরাসরি pymongo দিয়ে কানেক্ট করে —
    agno-র MongoDb wrapper-এর internal শেপের উপর নির্ভর না করে, যাতে
    agno ভার্সন বদলালেও এই মডিউল ভেঙে না যায়।"""
    from pymongo import MongoClient
    client = MongoClient(os.getenv("MONGODB_URI", "mongodb://localhost:27017"))
    return client[os.getenv("MONGODB_DB_NAME", "agno_system")]


def create_pending_approval(action: str, details: str) -> str:
    request_id = str(uuid.uuid4())
    with _lock:
        _pending[request_id] = {
            "event": threading.Event(),
            "decision": None,
            "action": action,
            "details": details,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    try:
        _raw_db()["agno_approvals"].insert_one({
            "_id": request_id, "action": action, "details": details,
            "status": "pending", "created_at": datetime.now(timezone.utc),
        })
    except Exception:
        pass  # audit log ব্যর্থ হলেও approval flow যেন না আটকায়
    return request_id


def resolve_approval(request_id: str, approved: bool) -> bool:
    with _lock:
        entry = _pending.get(request_id)
        if not entry:
            return False
        entry["decision"] = approved
        entry["event"].set()
    try:
        _raw_db()["agno_approvals"].update_one(
            {"_id": request_id},
            {"$set": {"status": "approved" if approved else "denied",
                       "resolved_at": datetime.now(timezone.utc)}},
        )
    except Exception:
        pass
    return True


def _finalize_wait(request_id: str, entry: dict, got_it: bool) -> bool:
    with _lock:
        decision = entry["decision"] if got_it else False
        _pending.pop(request_id, None)
    if not got_it:
        try:
            _raw_db()["agno_approvals"].update_one(
                {"_id": request_id},
                {"$set": {"status": "timeout", "resolved_at": datetime.now(timezone.utc)}},
            )
        except Exception:
            pass
    return bool(decision)


def wait_for_approval(request_id: str, timeout: int = APPROVAL_TIMEOUT_SECONDS) -> bool:
    """সিনক্রোনাস (ব্লকিং) ভার্সন — শুধু নন-async কনটেক্সট থেকে কল করার জন্য
    (যেমন CLI স্ক্রিপ্ট/টেস্ট)। asyncio event loop-এর ভেতর থেকে এটা সরাসরি কল
    কোরো না — বদলে `await wait_for_approval_async(...)` ব্যবহার করো, নাহলে পুরো
    সার্ভার পাঁচ মিনিট পর্যন্ত ফ্রিজ হয়ে যেতে পারে।"""
    entry = _pending.get(request_id)
    if not entry:
        return False
    got_it = entry["event"].wait(timeout=timeout)
    return _finalize_wait(request_id, entry, got_it)


async def wait_for_approval_async(request_id: str, timeout: int = APPROVAL_TIMEOUT_SECONDS) -> bool:
    """async-নিরাপদ ভার্সন — ব্লকিং `Event.wait()` আলাদা থ্রেডে চালায়
    (`asyncio.to_thread`), তাই মূল event loop কখনো আটকায় না এবং অন্য সব
    ইউজার/সেশনের রিকোয়েস্ট স্বাভাবিকভাবে সার্ভ হতে থাকে।"""
    entry = _pending.get(request_id)
    if not entry:
        return False
    got_it = await asyncio.to_thread(entry["event"].wait, timeout)
    return _finalize_wait(request_id, entry, got_it)


def list_pending_approvals() -> list[dict]:
    with _lock:
        return [
            {"id": rid, "action": e["action"], "details": e["details"], "created_at": e["created_at"]}
            for rid, e in _pending.items()
        ]


# ---------------------------------------------------------- agent-facing ---

class ApprovalTools(Toolkit):
    """যেকোনো এজেন্ট এই টুল দিয়ে ঝুঁকিপূর্ণ কাজের আগে মানুষের অনুমতি চাইবে।
    UI থেকে approve/deny না করা পর্যন্ত এজেন্ট আটকে থাকবে (ডিফল্ট ৫ মিনিট,
    এরপর auto-deny)।
    """

    def __init__(self, **kwargs):
        super().__init__(name="approval_tools", tools=[self.request_approval], **kwargs)

    async def request_approval(self, action: str, details: str) -> str:
        """একটা ঝুঁকিপূর্ণ action-এর জন্য মানুষের অনুমোদন চাও। ফলাফল না পাওয়া
        পর্যন্ত এই কল ব্লক করে রাখবে (approve/deny/timeout) — কিন্তু async হওয়ায়
        (ভেতরে `wait_for_approval_async` ব্যবহার করে) এই অপেক্ষার সময় সার্ভারের
        বাকি ইউজার/সেশন স্বাভাবিকভাবেই সার্ভ হতে থাকে, পুরো সার্ভার আটকায় না।

        Args:
            action: সংক্ষেপে কী কাজ করা হবে (যেমন "ফাইল ডিলিট", "মেসেজ পাঠানো",
                "পারচেজ", "নতুন এজেন্ট/টিম ফাইল তৈরি")
            details: বিস্তারিত — ঠিক কী হবে (কোন ফাইল, কার কাছে, কত টাকা, কোন কমান্ড ইত্যাদি)

        Returns:
            "approved" অথবা "denied (টাইমআউট বা ইউজার প্রত্যাখ্যান করেছে)"
        """
        request_id = create_pending_approval(action, details)
        approved = await wait_for_approval_async(request_id)
        return "approved" if approved else "denied (টাইমআউট বা ইউজার প্রত্যাখ্যান করেছে)"


# সব এজেন্টের instructions-এ এই লাইনটা যোগ করার জন্য — যেসব agent ঝুঁকিপূর্ণ কাজ
# করে (ফাইল ডিলিট/ওভাররাইট, মেসেজ/পোস্ট পাঠানো, টাকা খরচ, শেল কমান্ড, নতুন কোড ফাইল
# লেখা যা সিস্টেম বদলে দেয়) তাদের instructions list-এ এই constant যোগ করে দাও।
APPROVAL_INSTRUCTION = (
    "অপরিবর্তনীয় বা ঝুঁকিপূর্ণ যেকোনো কাজ (ফাইল ডিলিট/ওভাররাইট, বার্তা/পোস্ট পাঠানো, "
    "টাকা খরচ, শেল কমান্ড রান, নতুন কোড ফাইল লেখা যা সিস্টেম বদলে দেয়) করার ঠিক আগে "
    "অবশ্যই `request_approval` টুল কল করে মানুষের অনুমতি নাও। 'denied' এলে কাজটা "
    "না করে ইউজারকে জানিয়ে দাও।"
)
