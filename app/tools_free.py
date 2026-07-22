"""
tools_free.py
=============
Agno-র যেসব টুলকিটে কোনো এক্সট্রা API key লাগে না — সবগুলো এখানে এক জায়গায়।
প্রতিটা agent দরকার অনুযায়ী এখান থেকে সাব-সেট import করে ব্যবহার করবে,
যাতে প্রতিটা agent-কে অল্প কিছু প্রাসঙ্গিক টুল দিয়ে ফোকাসড রাখা যায়
(একটাতেই সব ৩০টা টুল দিলে মডেল কনফিউজড হয়ে যায়)।
"""
import os

# ---------- Search ----------
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.arxiv import ArxivTools
from agno.tools.wikipedia import WikipediaTools
from agno.tools.hackernews import HackerNewsTools
from agno.tools.pubmed import PubmedTools
from agno.tools.baidusearch import BaiduSearchTools

# ---------- Web scraping ----------
from agno.tools.newspaper4k import Newspaper4kTools
from agno.tools.website import WebsiteTools
from agno.tools.trafilatura import TrafilaturaTools
from agno.tools.crawl4ai import Crawl4aiTools

# ---------- Data ----------
from agno.tools.csv_toolkit import CsvTools
from agno.tools.duckdb import DuckDbTools
from agno.tools.pandas import PandasTools
from agno.tools.sql import SQLTools

# ---------- Local system ----------
from agno.tools.calculator import CalculatorTools
from agno.tools.file import FileTools
from agno.tools.shell import ShellTools
from agno.tools.python import PythonTools
from agno.tools.local_file_system import LocalFileSystemTools
from agno.tools.sleep import SleepTools

# ---------- অন্যান্য ফ্রি টুল ----------
from agno.tools.yfinance import YFinanceTools
from agno.tools.reasoning import ReasoningTools
from agno.tools.visualization import VisualizationTools
from agno.tools.webtools import WebTools
from agno.tools.webbrowser import WebBrowserTools
from agno.tools.llms_txt import LLMsTxtTools

# ---------- ভারী/হার্ডওয়্যার-নির্ভর ঐচ্ছিক টুল ----------
# এগুলো opencv/docling(torch)/moviepy-এর মতো ভারী প্যাকেজ চায়। হেডলেস/পোর্টেবল
# কন্টেইনারে এসব না থাকলেও যাতে পুরো সিস্টেম চালু হয়, তাই import ঐচ্ছিক রাখা হলো —
# প্যাকেজ ইনস্টল থাকলে (যেমন Noor OS-এ) টুলটা এমনিতেই যুক্ত হবে, আচরণ একই থাকবে।
try:
    from agno.tools.opencv import OpenCVTools
except Exception:
    OpenCVTools = None
try:
    from agno.tools.docling import DoclingTools
except Exception:
    DoclingTools = None
try:
    from agno.tools.moviepy_video import MoviePyVideoTools
except Exception:
    MoviePyVideoTools = None


SEARCH_TOOLS = [
    DuckDuckGoTools(),
    ArxivTools(),
    WikipediaTools(),
    HackerNewsTools(),
    PubmedTools(),
    BaiduSearchTools(),
]

SCRAPE_TOOLS = [
    Newspaper4kTools(),
    WebsiteTools(),
    TrafilaturaTools(),
    Crawl4aiTools(),
]

DATA_TOOLS = [
    CsvTools(),
    DuckDbTools(),
    PandasTools(),
    SQLTools(db_url=os.getenv("SQL_TOOLS_DB_URL", "sqlite:///agno_sql.db")),
    VisualizationTools(),
]

SYSTEM_TOOLS = [
    CalculatorTools(),
    FileTools(),
    ShellTools(),
    PythonTools(),
    LocalFileSystemTools(),
    SleepTools(),
]

FINANCE_TOOLS = [
    YFinanceTools(enable_stock_price=True, enable_company_info=True, enable_analyst_recommendations=True),
]

MISC_TOOLS = [
    ReasoningTools(add_instructions=True),
    WebTools(),
    WebBrowserTools(),
    LLMsTxtTools(),
]
# ঐচ্ছিক ভারী টুল — সংশ্লিষ্ট প্যাকেজ ইনস্টল থাকলেই যুক্ত হবে (নইলে স্কিপ)।
for _OptionalTool in (OpenCVTools, DoclingTools, MoviePyVideoTools):
    if _OptionalTool is not None:
        try:
            MISC_TOOLS.append(_OptionalTool())
        except Exception:
            pass

ALL_FREE_TOOLS = (
    SEARCH_TOOLS + SCRAPE_TOOLS + DATA_TOOLS + SYSTEM_TOOLS + FINANCE_TOOLS + MISC_TOOLS
)
