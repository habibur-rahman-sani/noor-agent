"""
memory_core.py
==============
"দীর্ঘমেয়াদী স্মৃতি" স্তর — ইউজার যা যা বলেছে তার সবকিছু কাঁচা আকারে চিরকাল context-এ
বয়ে বেড়ানোর বদলে, পুরনো কথোপকথন পর্যায়ক্রমে সংক্ষিপ্ত করে (সামারি বানিয়ে) রাখা এবং
পরে দরকার হলে সেই সামারি খুঁজে বের করে ব্যবহার করা।

এটা agno-র নিজস্ব `enable_agentic_memory` (config.py-র MEMORY_KWARGS, agno_memories
কালেকশনে সেভ হয়) থেকে **আলাদা এবং সম্পূরক**:
    - agno-র agentic memory: প্রতি turn-এ মডেল নিজে থেকে বিচ্ছিন্ন তথ্য (যেমন "ইউজারের
      প্রিয় রঙ নীল") বের করে রাখে — এটা agno-র নিজস্ব ব্ল্যাকবক্স, কনফিগার করা আছে,
      নতুন করে কিছু করার দরকার নেই।
    - এই মডিউল: গোটা কথোপকথন (session) সময়ে সময়ে ব্যাচ করে একটা মডেলকে দিয়ে
      সংক্ষিপ্ত/কাঠামোবদ্ধ করে (কী নিয়ে কথা হয়েছে, কী সিদ্ধান্ত হয়েছে, কী এখনো বাকি) —
      যাতে পুরনো পুরো কথোপকথন না রেখেও তার "সারমর্ম" ভবিষ্যতে কাজে লাগানো যায়।

ডিজাইন সিদ্ধান্ত:
    - কাঁচা কথোপকথন MongoDB-তেই থাকে (agno_conversation_log) — এই মডিউল কিছু ডিলিট করে
      না (ডিফল্টে), শুধু "সারাংশ হয়ে গেছে" ফ্ল্যাগ বসায়। ডেটা হারানোর ঝুঁকি ছাড়াই
      context-এ কম টেনে আনা যায়।
    - সামারাইজেশন ব্যর্থ হলে (মডেল/নেট সমস্যা) চুপচাপ স্কিপ হয়, পরের বার আবার চেষ্টা হবে —
      কোনো ডেটা হারায় না, ক্র্যাশও করে না।
    - recall_context একটা সাধারণ keyword/substring সার্চ (MongoDB $regex) — ভেক্টর
      সার্চ/এমবেডিং ইনফ্রা নেই, তাই খুব বড় ডেটাসেটে নিখুঁত না, কিন্তু নির্ভরযোগ্য ও কোনো
      এক্সট্রা ডিপেন্ডেন্সি ছাড়াই কাজ করে।
"""
import logging
from datetime import datetime, timedelta, timezone

from agno.tools.toolkit import Toolkit
from config import ask_text_model

logger = logging.getLogger("memory_core")

CONV_COLLECTION = "agno_conversation_log"
SUMMARY_COLLECTION = "agno_memory_summaries"
NOTES_COLLECTION = "agno_notes"

SUMMARIZE_JOB_ID = "internal_memory_summarize"
DEFAULT_MIN_AGE_HOURS = 6   # এত ঘণ্টা পুরনো না হলে সামারাইজ করা হবে না (চলতি কথোপকথন এড়াতে)
DEFAULT_INTERVAL_HOURS = 6  # কত ঘণ্টা পরপর সামারাইজেশন জব চলবে


def _get_mongo_collection(name: str):
    import os
    from pymongo import MongoClient
    client = MongoClient(os.getenv("MONGODB_URI", "mongodb://localhost:27017"))
    db = client[os.getenv("MONGODB_DB_NAME", "agno_system")]
    return db[name]


# --------------------------------------------------------------- logging ---

def log_exchange(session_id: str, user_message: str, response_text: str) -> None:
    """প্রতিটা চ্যাট-এক্সচেঞ্জ (ইউজার মেসেজ + সিস্টেমের পূর্ণ উত্তর) এখানে সেভ হয় —
    server.py-র /api/chat আর /ws/chat দুটো থেকেই ডাকা হয়, ঠিক _log_trace-এর পাশে।
    ব্যর্থ হলে (Mongo বন্ধ থাকলে ইত্যাদি) চ্যাট আটকায় না, শুধু লগ হয় ও চুপচাপ স্কিপ হয়।
    """
    try:
        _get_mongo_collection(CONV_COLLECTION).insert_one({
            "session_id": session_id,
            "user_message": user_message,
            "response_text": response_text,
            "at": datetime.now(timezone.utc),
            "summarized": False,
        })
    except Exception:
        logger.exception("কথোপকথন লগ করা যায়নি (Mongo সমস্যা?) — মেমোরি সামারাইজেশন এই এন্ট্রিটা মিস করবে।")


# ---------------------------------------------------------- summarization ---

def summarize_pending(min_age_hours: int = DEFAULT_MIN_AGE_HOURS, max_sessions: int = 20) -> dict:
    """যেসব session-এর এন্ট্রি এখনো সামারাইজ হয়নি এবং যথেষ্ট পুরনো (চলতি কথোপকথন এড়াতে),
    সেগুলো session-ভিত্তিক ব্যাচ করে একটা মডেলকে দিয়ে সংক্ষিপ্ত করে agno_memory_summaries-এ
    সেভ করে। এটা scheduler.py-র মাধ্যমে পর্যায়ক্রমিক জব হিসেবে চলে (register_internal_jobs
    দেখো), কিন্তু ম্যানুয়ালিও ডাকা যায় (যেমন টেস্ট করার জন্য)।

    রিটার্ন করে: {"sessions_summarized": int, "errors": [...]}। raw এন্ট্রি ডিলিট করে না,
    শুধু "summarized": True ফ্ল্যাগ বসায় — ডেটা হারানোর ঝুঁকি নেই।
    """
    try:
        conv = _get_mongo_collection(CONV_COLLECTION)
        summaries = _get_mongo_collection(SUMMARY_COLLECTION)
    except Exception as e:  # noqa: BLE001
        return {"sessions_summarized": 0, "errors": [f"Mongo কানেকশন ব্যর্থ: {e}"]}

    cutoff = datetime.now(timezone.utc) - timedelta(hours=min_age_hours)
    pending_sessions = conv.distinct("session_id", {"summarized": False, "at": {"$lt": cutoff}})

    if not pending_sessions:
        return {"sessions_summarized": 0, "errors": []}

    errors = []
    done = 0
    for session_id in pending_sessions[:max_sessions]:
        entries = list(conv.find(
            {"session_id": session_id, "summarized": False, "at": {"$lt": cutoff}}
        ).sort("at", 1))
        if not entries:
            continue

        transcript = "\n\n".join(
            f"ইউজার: {e['user_message'][:800]}\nসিস্টেম: {e['response_text'][:800]}"
            for e in entries
        )
        prompt = (
            "নিচে একটা ইউজার আর AI সিস্টেমের কথোপকথনের অংশ দেওয়া আছে। এর একটা সংক্ষিপ্ত, "
            "কাঠামোবদ্ধ সারাংশ বানাও — শুধু ভবিষ্যতে কাজে লাগবে এমন স্থায়ী/গুরুত্বপূর্ণ তথ্য রাখো "
            "(ইউজারের পছন্দ, সিদ্ধান্ত, চলমান কাজ, উল্লেখযোগ্য তথ্য), সাধারণ ভদ্রতা/খুচরা কথাবার্তা বাদ দাও। "
            "বুলেট পয়েন্ট আকারে, বাংলায়, সংক্ষেপে লেখো (সর্বোচ্চ ১৫০ শব্দ)।\n\n"
            f"--- কথোপকথন ---\n{transcript}"
        )

        result = ask_text_model(prompt, task="reasoning", max_tokens=400)
        if result["status"] != "ok":
            errors.append(f"session {session_id}: {result['error']}")
            continue  # এই session পরের রানে আবার চেষ্টা হবে (summarized ফ্ল্যাগ বসেনি)

        try:
            summaries.insert_one({
                "session_id": session_id,
                "summary_text": result["text"].strip(),
                "covers_from": entries[0]["at"],
                "covers_to": entries[-1]["at"],
                "entry_count": len(entries),
                "created_at": datetime.now(timezone.utc),
            })
            entry_ids = [e["_id"] for e in entries]
            conv.update_many({"_id": {"$in": entry_ids}}, {"$set": {"summarized": True}})
            done += 1
        except Exception as e:  # noqa: BLE001
            errors.append(f"session {session_id}: সেভ ব্যর্থ ({e})")

    return {"sessions_summarized": done, "errors": errors}


def register_internal_jobs(sched) -> None:
    """server.py-র স্টার্টআপে একবার ডাকা হয় (start_scheduler()-এর পরে) — পর্যায়ক্রমিক
    মেমোরি-সামারাইজেশন জব বসায়। id ফিক্সড + replace_existing=True, তাই সার্ভার বারবার
    রিস্টার্ট হলেও ডুপ্লিকেট জব তৈরি হয় না।"""
    try:
        sched.add_job(
            summarize_pending, "interval", hours=DEFAULT_INTERVAL_HOURS,
            id=SUMMARIZE_JOB_ID, replace_existing=True,
        )
        logger.info("মেমোরি-সামারাইজেশন জব শিডিউল হয়েছে (প্রতি %d ঘণ্টায়)।", DEFAULT_INTERVAL_HOURS)
    except Exception:
        logger.exception("মেমোরি-সামারাইজেশন জব শিডিউল করা যায়নি — সার্ভার চালু হতে বাধা দেয়নি।")


# --------------------------------------------------------------- recall ---

def recall_context(query: str, limit: int = 5) -> list[dict]:
    """সংরক্ষিত সামারি + এক্সপ্লিসিট নোট থেকে query-র সাথে সম্পর্কিত (সাধারণ কীওয়ার্ড
    ম্যাচ) এন্ট্রি খুঁজে বের করে, সাম্প্রতিকতম আগে। এমবেডিং/ভেক্টর সার্চ না — সহজ ও
    নির্ভরযোগ্য, কিন্তু ভিন্ন শব্দ ব্যবহার করলে মিস হতে পারে।"""
    results = []
    try:
        summaries = _get_mongo_collection(SUMMARY_COLLECTION)
        for doc in summaries.find(
            {"summary_text": {"$regex": query, "$options": "i"}}
        ).sort("created_at", -1).limit(limit):
            results.append({
                "type": "summary", "text": doc["summary_text"],
                "at": doc.get("created_at"), "session_id": doc.get("session_id"),
            })
    except Exception:
        logger.exception("সামারি খোঁজা যায়নি।")

    try:
        notes = _get_mongo_collection(NOTES_COLLECTION)
        for doc in notes.find(
            {"text": {"$regex": query, "$options": "i"}}
        ).sort("created_at", -1).limit(limit):
            results.append({"type": "note", "text": doc["text"], "at": doc.get("created_at")})
    except Exception:
        logger.exception("নোট খোঁজা যায়নি।")

    return results[:limit]


def save_note(text: str) -> None:
    """ইউজার/এজেন্ট এক্সপ্লিসিটলি "এটা মনে রাখো" বললে এখানে সেভ হয় — এটা কখনো
    সামারাইজ/মুছে ফেলা হয় না, সরাসরি recall_context-এ পাওয়া যাবে।"""
    _get_mongo_collection(NOTES_COLLECTION).insert_one({
        "text": text, "created_at": datetime.now(timezone.utc),
    })


# ------------------------------------------------------------ agent tools ---

class MemoryTools(Toolkit):
    """যেকোনো Agent/Team-এ যোগ করা যায় — এক্সপ্লিসিট মনে-রাখা ও পুরনো সংক্ষিপ্ত
    প্রসঙ্গ খুঁজে বের করার টুল। এটা agno-র নিজস্ব agentic memory প্রতিস্থাপন করে না,
    বরং session-সামারি-ভিত্তিক দীর্ঘমেয়াদী প্রসঙ্গ যোগ করে।"""

    def __init__(self, **kwargs):
        super().__init__(
            name="memory_tools",
            tools=[self.save_important_note, self.recall_past_context],
            **kwargs,
        )

    def save_important_note(self, text: str) -> str:
        """একটা গুরুত্বপূর্ণ তথ্য স্থায়ীভাবে মনে রাখার জন্য সেভ করো — ইউজার স্পষ্টভাবে
        "মনে রেখো" বললে, বা এমন কিছু জানলে যা ভবিষ্যতেও কাজে লাগবে বলে মনে হয়।

        Args:
            text: যা মনে রাখতে হবে, সংক্ষেপে ও স্পষ্টভাবে লেখো (একটা স্বয়ংসম্পূর্ণ বাক্য/অনুচ্ছেদ)
        """
        try:
            save_note(text)
            return "মনে রাখা হয়েছে।"
        except Exception as e:  # noqa: BLE001
            return f"সেভ করা যায়নি (Mongo সমস্যা?): {e}"

    def recall_past_context(self, query: str) -> str:
        """আগের কথোপকথন থেকে সংক্ষিপ্ত প্রসঙ্গ/নোট খুঁজে বের করো — বর্তমান কথোপকথনের
        num_history_runs=10-এর বাইরের পুরনো কিছু দরকার হলে এটা ব্যবহার করো।

        Args:
            query: কী বিষয়ে পুরনো প্রসঙ্গ দরকার (কীওয়ার্ড, সাধারণ ভাষায় সার্চ না)
        """
        matches = recall_context(query)
        if not matches:
            return f"'{query}' নিয়ে কোনো সংরক্ষিত পুরনো প্রসঙ্গ/নোট পাওয়া যায়নি।"
        lines = []
        for m in matches:
            tag = "নোট" if m["type"] == "note" else "সারাংশ"
            lines.append(f"[{tag}] {m['text']}")
        return "\n".join(lines)
