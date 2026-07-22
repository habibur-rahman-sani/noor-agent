"""
Meta এজেন্ট — সিস্টেম নিজে নিজেকে প্রসারিত করতে পারা (self-extension)। এটাই
"AI OS"-এর সবচেয়ে শক্তিশালী কিন্তু সবচেয়ে ঝুঁকিপূর্ণ এজেন্ট — এটা `teams/` ও
`agents/` ফোল্ডারে নতুন `.py` ফাইল লিখতে পারে, যা `teams/registry.py` অটোমেটিক
লোড করে নেয় (মানে এই এজেন্ট চালু সিস্টেমকে সত্যিই বদলে দিতে পারে)।

এই কারণে:
- এটা **শুধুমাত্র `teams/` ও `agents/` ফোল্ডারে** ফাইল লিখতে পারে (path সীমাবদ্ধ)।
- ফাইল লেখার **আগে বাধ্যতামূলক approval লাগবে** (guardrail.py, request_approval)।
- এটা existing ফাইল ওভাররাইট করতে পারবে না, শুধু নতুন ফাইল তৈরি করতে পারবে।
"""
from pathlib import Path

from agno.agent import Agent
from agno.tools.toolkit import Toolkit
from config import get_model, get_db, MEMORY_KWARGS
from guardrail import ApprovalTools, APPROVAL_INSTRUCTION

PROJECT_ROOT = Path(__file__).parent.parent
ALLOWED_DIRS = {"teams", "agents"}


class SelfExtensionTools(Toolkit):
    """নতুন Team/Agent ফাইল লেখার জন্য পাথ-সীমাবদ্ধ, ওভাররাইট-প্রতিরোধী টুল।"""

    def __init__(self, **kwargs):
        super().__init__(name="self_extension_tools", tools=[self.write_new_module, self.read_module], **kwargs)

    def read_module(self, relative_path: str) -> str:
        """বিদ্যমান কোনো team/agent ফাইল পড়ো (নতুন ফাইল লেখার আগে প্যাটার্ন বোঝার জন্য)।

        Args:
            relative_path: যেমন "teams/coding_team.py" বা "agents/coding_agent.py"
        """
        path = (PROJECT_ROOT / relative_path).resolve()
        if not str(path).startswith(str(PROJECT_ROOT)):
            return "অবৈধ path।"
        if not path.exists():
            return f"'{relative_path}' পাওয়া যায়নি।"
        return path.read_text(encoding="utf-8")

    def write_new_module(self, relative_path: str, content: str) -> str:
        """`teams/` অথবা `agents/`-এ একটা **নতুন** .py ফাইল লেখো (বিদ্যমান ফাইল ওভাররাইট করা যাবে না)।
        লেখার আগে অবশ্যই `request_approval` টুল দিয়ে অনুমতি নিতে হবে।

        Args:
            relative_path: যেমন "teams/finance_advisor_team.py" (শুধু teams/ বা agents/ ফোল্ডারে)
            content: সম্পূর্ণ ফাইল কনটেন্ট। team ফাইলে অবশ্যই `team = Team(...)` ভ্যারিয়েবল থাকতে হবে,
                agent ফাইলে অবশ্যই একটা Agent instance এক্সপোর্ট করা ভ্যারিয়েবল থাকতে হবে।
        """
        parts = Path(relative_path).parts
        if not parts or parts[0] not in ALLOWED_DIRS:
            return f"শুধু {ALLOWED_DIRS} ফোল্ডারে নতুন ফাইল লেখা যাবে।"
        if not relative_path.endswith(".py"):
            return "শুধু .py ফাইল লেখা যাবে।"

        path = (PROJECT_ROOT / relative_path).resolve()
        if not str(path).startswith(str(PROJECT_ROOT)):
            return "অবৈধ path — প্রজেক্ট ফোল্ডারের বাইরে লেখা যাবে না।"
        if path.exists():
            return f"'{relative_path}' ইতিমধ্যে আছে — এই টুল দিয়ে বিদ্যমান ফাইল ওভাররাইট করা যায় না।"

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return (
            f"'{relative_path}' তৈরি হয়েছে। এটা registry.py দিয়ে অটো-লোড হবে **পরের বার সার্ভার "
            "রিস্টার্ট হলে** (চলমান প্রসেসে মাঝপথে নতুন টিম যোগ হয় না) — ইউজারকে সার্ভার রিস্টার্ট "
            "করতে বলো।"
        )


meta_agent = Agent(
    name="Meta Agent",
    role="সিস্টেমের নিজের কাঠামো বোঝা এবং নতুন Team/Agent ফাইল লিখে সিস্টেমকে প্রসারিত করা (self-extension)",
    model=get_model("coding"),
    db=get_db(),
    tools=[SelfExtensionTools(), ApprovalTools()],
    instructions=[
        "নতুন কিছু লেখার আগে অবশ্যই read_module দিয়ে একটা কাছাকাছি বিদ্যমান team/agent ফাইল পড়ে "
        "সেই একই প্যাটার্ন অনুসরণ করো (README.md-এর 'নতুন টিম যোগ করা' সেকশনও অনুসরণযোগ্য)।",
        "write_new_module কল করার আগে অবশ্যই " + APPROVAL_INSTRUCTION,
        "team ফাইলে `team = Team(...)` এবং agent ফাইলে একটা এক্সপোর্ট করা Agent ভ্যারিয়েবল থাকা "
        "বাধ্যতামূলক — নাহলে registry.py সেটা লোড করবে না।",
        "ফাইল লেখার পর ইউজারকে বলো যে সার্ভার রিস্টার্ট করলে নতুন টিম/এজেন্ট সক্রিয় হবে।",
    ],
    markdown=True,
    **MEMORY_KWARGS,
)
