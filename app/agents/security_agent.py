"""
Security এজেন্ট — AI OS-এর "safety layer"। দুটো কাজ করে:
1. অন্য এজেন্টদের হয়ে ঝুঁকিপূর্ণ কাজের approval-request পরিচালনা (guardrail.py)
2. ছোট credential vault — API key/পাসওয়ার্ডের মতো স্পর্শকাতর তথ্য সরাসরি
   .env-এর বাইরে, এনক্রিপ্ট করে MongoDB-তে রাখা (SECURITY_VAULT_KEY থাকলে
   `cryptography`-র Fernet দিয়ে এনক্রিপ্ট হয়, না থাকলে সিস্টেম কাজ করবে কিন্তু
   warning দেখাবে যে এনক্রিপশন ছাড়া সেভ হচ্ছে)।
"""
import os

from agno.agent import Agent
from agno.tools.toolkit import Toolkit
from config import get_model, get_db, MEMORY_KWARGS
from guardrail import ApprovalTools, list_pending_approvals


def _raw_db():
    from pymongo import MongoClient
    client = MongoClient(os.getenv("MONGODB_URI", "mongodb://localhost:27017"))
    return client[os.getenv("MONGODB_DB_NAME", "agno_system")]


def _fernet():
    key = os.getenv("SECURITY_VAULT_KEY")
    if not key:
        return None
    from cryptography.fernet import Fernet
    return Fernet(key.encode())


class VaultTools(Toolkit):
    """ছোট credential vault — স্পর্শকাতর তথ্য (key/টোকেন/পাসওয়ার্ড) সংরক্ষণ ও পড়া।"""

    def __init__(self, **kwargs):
        super().__init__(name="vault_tools", tools=[self.vault_store, self.vault_get, self.vault_list], **kwargs)

    def vault_store(self, name: str, value: str) -> str:
        """একটা স্পর্শকাতর মান vault-এ সেভ করো।

        Args:
            name: এই ভ্যালুর নাম/আইডি (যেমন "personal_email_password")
            value: আসল স্পর্শকাতর মান
        """
        f = _fernet()
        stored = f.encrypt(value.encode()).decode() if f else value
        try:
            _raw_db()["agno_vault"].update_one(
                {"_id": name}, {"$set": {"value": stored, "encrypted": bool(f)}}, upsert=True
            )
        except Exception as e:  # noqa: BLE001
            return f"Vault-এ সেভ ব্যর্থ হয়েছে: {e}"
        warn = "" if f else " ⚠️ SECURITY_VAULT_KEY সেট নেই বলে এনক্রিপশন ছাড়া সেভ হয়েছে।"
        return f"'{name}' vault-এ সেভ হয়েছে।{warn}"

    def vault_get(self, name: str) -> str:
        """vault থেকে একটা মান বের করো।

        Args:
            name: যেই নামে সেভ করা হয়েছিল
        """
        try:
            doc = _raw_db()["agno_vault"].find_one({"_id": name})
        except Exception as e:  # noqa: BLE001
            return f"Vault পড়া যায়নি: {e}"
        if not doc:
            return f"'{name}' নামে vault-এ কিছু পাওয়া যায়নি।"
        if doc.get("encrypted"):
            f = _fernet()
            if not f:
                return "এই মানটা এনক্রিপ্ট করা কিন্তু SECURITY_VAULT_KEY এখন সেট নেই — ডিক্রিপ্ট করা যাচ্ছে না।"
            try:
                return f.decrypt(doc["value"].encode()).decode()
            except Exception as e:  # noqa: BLE001
                return f"ডিক্রিপ্ট ব্যর্থ: {e}"
        return doc["value"]

    def vault_list(self) -> str:
        """vault-এ কী কী নাম সেভ আছে তার তালিকা (মান দেখায় না)।"""
        try:
            names = [d["_id"] for d in _raw_db()["agno_vault"].find({}, {"_id": 1})]
        except Exception as e:  # noqa: BLE001
            return f"Vault পড়া যায়নি: {e}"
        return ", ".join(names) if names else "vault খালি।"


class ApprovalAdminTools(Toolkit):
    """পেন্ডিং approval-request দেখার টুল (নিজে approve/deny করে না — সেটা শুধু মানুষ UI থেকে করবে)।"""

    def __init__(self, **kwargs):
        super().__init__(name="approval_admin_tools", tools=[self.list_pending], **kwargs)

    def list_pending(self) -> str:
        """এখন কোন কোন ঝুঁকিপূর্ণ action মানুষের অনুমোদনের অপেক্ষায় আছে তা দেখাও।"""
        pending = list_pending_approvals()
        if not pending:
            return "এই মুহূর্তে কোনো action অনুমোদনের অপেক্ষায় নেই।"
        return "\n".join(f"- [{p['id'][:8]}] {p['action']}: {p['details']}" for p in pending)


security_tools = [ApprovalTools(), VaultTools(), ApprovalAdminTools()]

security_agent = Agent(
    name="Security Agent",
    role="ঝুঁকিপূর্ণ action-এ approval-gate পরিচালনা এবং স্পর্শকাতর তথ্যের জন্য ছোট encrypted vault",
    model=get_model("general"),
    db=get_db(),
    tools=security_tools,
    instructions=[
        "vault-এ কোনো মান স্টোর করার আগে বুঝিয়ে দাও এটা কোথায়/কীভাবে সেভ হচ্ছে (এনক্রিপ্টেড কিনা)।",
        "vault_get দিয়ে আনা মান কখনো অপ্রয়োজনে সরাসরি চ্যাটে দেখিও না যদি ইউজার স্পষ্টভাবে না চায়।",
        "list_pending দিয়ে ঝুঁকিপূর্ণ কাজের অনুমোদনের অবস্থা ইউজারকে জানাতে পারো।",
    ],
    markdown=True,
    **MEMORY_KWARGS,
)
