"""
Personal Knowledge এজেন্ট — ইউজারের নিজস্ব ফাইল/নোট নিয়ে দীর্ঘমেয়াদি জ্ঞান।
এই ভার্সনটা সততার সাথে সরল রাখা হয়েছে: PERSONAL_DOCS_DIR ফোল্ডারের টেক্সট-জাতীয়
ফাইলে (txt/md) কীওয়ার্ড-ভিত্তিক সার্চ করে (fuzzy পূর্ণাঙ্গ ভেক্টর সার্চ না)।

**পরের ধাপে upgrade করার জায়গা**: প্রকৃত semantic/vector RAG চাইলে একটা লোকাল
ভেক্টর DB (যেমন LanceDb/Chroma, key ছাড়াই চলে) যোগ করে embedding-ভিত্তিক
সার্চে বদলানো যায় — এখন সেটা যোগ করা হয়নি যাতে অতিরিক্ত ভারী dependency
(embedding মডেল) ছাড়াই কাজ চলে।
"""
import os
from pathlib import Path

from agno.agent import Agent
from agno.tools.toolkit import Toolkit
from config import get_model, get_db, MEMORY_KWARGS


def _docs_dir() -> Path:
    return Path(os.getenv("PERSONAL_DOCS_DIR", "./personal_docs")).expanduser()


class PersonalDocsTools(Toolkit):
    """PERSONAL_DOCS_DIR-এ রাখা ব্যক্তিগত txt/md ফাইলে কীওয়ার্ড সার্চ করার টুল।"""

    def __init__(self, **kwargs):
        super().__init__(name="personal_docs_tools", tools=[self.search_personal_docs, self.list_personal_docs], **kwargs)

    def list_personal_docs(self) -> str:
        """PERSONAL_DOCS_DIR-এ কী কী ফাইল আছে তার তালিকা।"""
        d = _docs_dir()
        if not d.exists():
            return f"'{d}' ফোল্ডার নেই। .env-এ PERSONAL_DOCS_DIR সেট করো এবং ফোল্ডারটা তৈরি করো।"
        files = [str(p.relative_to(d)) for p in d.rglob("*") if p.suffix.lower() in (".txt", ".md")]
        return "\n".join(files) if files else "ফোল্ডারে কোনো .txt/.md ফাইল পাওয়া যায়নি।"

    def search_personal_docs(self, query: str, max_matches: int = 5) -> str:
        """ব্যক্তিগত নোট/ডকুমেন্টে কীওয়ার্ড সার্চ করে প্রাসঙ্গিক অংশ বের করে।

        Args:
            query: কী খুঁজছো
            max_matches: সর্বোচ্চ কতগুলো ম্যাচ ফেরত দেবে
        """
        d = _docs_dir()
        if not d.exists():
            return f"'{d}' ফোল্ডার নেই। .env-এ PERSONAL_DOCS_DIR সেট করো।"

        terms = [t.lower() for t in query.split() if t.strip()]
        matches = []
        for path in d.rglob("*"):
            if path.suffix.lower() not in (".txt", ".md"):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            lower = text.lower()
            if any(t in lower for t in terms):
                idx = lower.find(terms[0]) if terms else 0
                start = max(0, idx - 150)
                snippet = text[start:idx + 350].strip()
                matches.append(f"[{path.relative_to(d)}] ...{snippet}...")
            if len(matches) >= max_matches:
                break
        return "\n\n".join(matches) if matches else "কোনো মিল পাওয়া যায়নি।"


personal_knowledge_agent = Agent(
    name="Personal Knowledge Agent",
    role="ইউজারের নিজস্ব নোট/ডকুমেন্ট (PERSONAL_DOCS_DIR) থেকে তথ্য খুঁজে বের করা — দীর্ঘমেয়াদি ব্যক্তিগত জ্ঞান",
    model=get_model("research"),
    db=get_db(),
    tools=[PersonalDocsTools()],
    instructions=[
        "শুধু .txt/.md ফাইলে কীওয়ার্ড-ভিত্তিক সার্চ করতে পারো — এটা প্রাথমিক সংস্করণ, "
        "semantic/vector সার্চ না, তাই মাঝেমধ্যে প্রাসঙ্গিক কিছু মিস হতে পারে সেটা মাথায় রাখো।",
        "ফোল্ডার খালি/অনুপস্থিত হলে ইউজারকে PERSONAL_DOCS_DIR সেটআপ করতে বলো।",
    ],
    markdown=True,
    **MEMORY_KWARGS,
)
