"""
কোডিং এজেন্ট — এইটার লক্ষ্য: কোডিং-সংক্রান্ত যা কিছু সম্ভব সব করতে পারা
(লেখা, রান করা, ডিবাগ করা, রিফ্যাক্টর করা, রিপো ম্যানেজ করা, সন্ডবক্সে টেস্ট করা)।

নিরাপত্তা ফিক্স: raw agno ShellTools/FileTools-এর বদলে safety_tools.py-র
SafeShellTools/SafeFileTools ব্যবহার করা হয় — approval কোডে বাধ্যতামূলক, আর
ফাইল ডিলিট/ওভাররাইট স্বয়ংক্রিয়ভাবে ব্যাকআপ হয়ে undo করা যায়।
"""
from agno.agent import Agent
from agno.tools.calculator import CalculatorTools
from agno.tools.python import PythonTools
from agno.tools.sleep import SleepTools
from config import get_model, get_db, has_key, MEMORY_KWARGS
from tools_free import DATA_TOOLS
from guardrail import ApprovalTools, APPROVAL_INSTRUCTION
from safety_tools import SafeShellTools, SafeFileTools

coding_tools = [
    CalculatorTools(), PythonTools(), SleepTools(),
    SafeShellTools(), SafeFileTools(),
    ApprovalTools(),
] + [t for t in DATA_TOOLS if t.name in ("duckdb_tools", "sql_tools", "pandas_tools")]

# Docker — লোকালি ইনস্টল করা থাকলেই কাজ করে, key লাগে না
try:
    from agno.tools.docker import DockerTools
    coding_tools.append(DockerTools())
except Exception:
    pass

# GitHub — রিপো/ইস্যু/PR ম্যানেজমেন্ট (ফ্রি অ্যাকাউন্ট, personal access token লাগবে)
if has_key("GITHUB_ACCESS_TOKEN"):
    from agno.tools.github import GithubTools
    coding_tools.append(GithubTools())

# GitLab
if has_key("GITLAB_ACCESS_TOKEN"):
    from agno.tools.gitlab import GitlabTools
    coding_tools.append(GitlabTools())

# Morph AI — দ্রুত, নির্ভুল কোড এডিট/প্যাচ (পেইড)
if has_key("MORPH_API_KEY"):
    from agno.tools.models.morph import MorphTools
    coding_tools.append(MorphTools())

# E2B — আইসোলেটেড কোড-এক্সিকিউশন সন্ডবক্স (পেইড, ফ্রি টিয়ার আছে)
if has_key("E2B_API_KEY"):
    from agno.tools.e2b import E2BTools
    coding_tools.append(E2BTools())

# Daytona — রিমোট সন্ডবক্সে কোড রান (পেইড, ফ্রি টিয়ার আছে)
if has_key("DAYTONA_API_KEY"):
    from agno.tools.daytona import DaytonaTools
    coding_tools.append(DaytonaTools())

coding_agent = Agent(
    name="Coding Agent",
    role="সফটওয়্যার ডেভেলপমেন্টের যেকোনো কাজ: কোড লেখা, রান করা, ডিবাগ, রিফ্যাক্টর, টেস্ট, রিপো/PR ম্যানেজমেন্ট, সন্ডবক্স এক্সিকিউশন",
    model=get_model("coding"),
    db=get_db(),
    tools=coding_tools,
    instructions=[
        "কাজ শুরুর আগে সংক্ষেপে প্ল্যান করো (ধাপে ধাপে)।",
        "শেল কমান্ড run_shell_command দিয়ে, ফাইল লেখা/ডিলিট SafeFileTools দিয়ে করো — দুটোই কোডে "
        "বাধ্যতামূলক approval-gated। গিট পুশ/ফোর্স-পুশের মতো ঝুঁকিপূর্ণ কাজের আগেও " + APPROVAL_INSTRUCTION,
        "ফাইল ভুল করে ডিলিট/ওভাররাইট হলে undo_last_file_change দিয়ে ফেরানো যায়।",
        "কোড রান করার পর আউটপুট/এরর সরাসরি দেখাও।",
        "যেই টুল/key নেই সেটার জন্য বিকল্প উপায় বলো (যেমন Docker না থাকলে সরাসরি শেলে রান করা)।",
    ],
    markdown=True,
    **MEMORY_KWARGS,
)
