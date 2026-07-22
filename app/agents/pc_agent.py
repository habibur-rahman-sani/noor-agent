"""
PC এজেন্ট — কম্পিউটারে প্রোগ্রাম চালানো, ফাইল ম্যানেজমেন্ট, স্ক্রিপ্ট অটোমেশন,
এবং মাউস/কীবোর্ড/উইন্ডো/ক্লিপবোর্ড দিয়ে সরাসরি ডেস্কটপ নিয়ন্ত্রণ — মানুষ যা যা করতে
পারে প্রায় তাই।

নিরাপত্তা ফিক্স: আগে এখানে raw agno `ShellTools`/`FileTools` সরাসরি দেওয়া ছিল,
যেগুলোর কোনো approval-gate কোডে enforce করা ছিল না (শুধু prompt-এ লেখা ছিল,
মডেল ভুলে গেলে বাইপাস হয়ে যেত)। এখন safety_tools.py-র SafeShellTools/SafeFileTools
ব্যবহার করা হচ্ছে — শেল কমান্ড ও ফাইল ডিলিট/ওভাররাইট কোডেই বাধ্যতামূলক
approval-gate পার হয় (fail-closed), আর ডিলিট/ওভাররাইট স্বয়ংক্রিয়ভাবে ব্যাকআপ
হয়ে undo_last_file_change দিয়ে ফেরানো যায়।

আরও একটা ফাঁক ফিক্স করা হয়েছে: আগে টেক্সট-বিহীন আইকন-শুধু বাটনে ক্লিক করা সম্ভব ছিল না
(click_text/locate_text পুরোপুরি OCR-নির্ভর)। এখন desktop_control.py-তে click_icon আছে,
যা একটা মাল্টিমোডাল vision-LLM-কে স্ক্রিনশট পাঠিয়ে আইকনের কোঅর্ডিনেট বের করে ক্লিক করে —
এটাই OCR-বিহীন GUI উপাদানের জন্য বাস্তব "computer-use" ফলব্যাক। এটা click_text-এর চেয়ে
ধীর/ব্যয়সাপেক্ষ, তাই টেক্সট-লেবেলযুক্ত জিনিসে আগে click_text-ই ব্যবহার করা উচিত।
"""
from agno.agent import Agent
from agno.tools.calculator import CalculatorTools
from agno.tools.python import PythonTools
from agno.tools.sleep import SleepTools
from config import get_model, get_db, MEMORY_KWARGS
from guardrail import ApprovalTools, APPROVAL_INSTRUCTION
from desktop_control import DesktopControlTools
from safety_tools import SafeShellTools, SafeFileTools

pc_agent = Agent(
    name="PC Agent",
    role="কম্পিউটারে প্রোগ্রাম চালানো, ফাইল ম্যানেজমেন্ট, এবং মাউস/কীবোর্ড/উইন্ডো/ক্লিপবোর্ড দিয়ে সরাসরি ডেস্কটপ নিয়ন্ত্রণ — মানুষ যা যা করতে পারে প্রায় তাই",
    model=get_model("coding"),
    db=get_db(),
    tools=[
        CalculatorTools(), PythonTools(), SleepTools(),
        SafeShellTools(), SafeFileTools(),
        ApprovalTools(), DesktopControlTools(),
    ],
    instructions=[
        "টেক্সট/বাটন-লেবেল দেখে ক্লিক করতে হলে সবচেয়ে সহজ উপায় click_text(query) ব্যবহার করো — "
        "এটা একসাথে খুঁজে বের করে ও ক্লিক করে। একাধিক ম্যাচ পেলে বা নিশ্চিত না হলে আগে locate_text "
        "(Vision Agent-এর মাধ্যমে) দিয়ে সব ম্যাচ দেখে যাচাই করে নাও।",
        "আইকন-শুধু বাটনে (কোনো টেক্সট নেই) click_text/locate_text কাজ করবে না (OCR-ভিত্তিক) — "
        "সেক্ষেত্রে click_icon(বর্ণনা) ব্যবহার করো (vision-LLM দিয়ে দেখে কোঅর্ডিনেট বের করে ক্লিক করে)। "
        "এটাও ব্যর্থ/অনিশ্চিত হলে ইউজারকে স্পষ্টভাবে বলো এবং বিকল্প (কীবোর্ড শর্টকাট/মেনু) খোঁজো।",
        "সরাসরি কোঅর্ডিনেট জানা থাকলে move_and_click/type_text/press_key ব্যবহার করো।",
        "উইন্ডো ম্যানেজমেন্টের জন্য list_windows/focus_window/close_window ব্যবহার করো।",
        "নতুন অ্যাপ চালু করতে launch_application ব্যবহার করো — এটা approval-gated।",
        "শেল কমান্ড run_shell_command দিয়ে চালাও, ফাইল লেখা/ডিলিট SafeFileTools "
        "(write_file/append_file/delete_file) দিয়ে করো — দুটোই কোডে বাধ্যতামূলক "
        "approval-gated, এড়ানোর দরকার নেই বা সম্ভবও না।",
        "ফাইল ডিলিট/ওভাররাইট ভুল হয়ে গেলে বা ইউজার আনডু চাইলে undo_last_file_change ব্যবহার করো "
        "(সবচেয়ে সাম্প্রতিক পরিবর্তন ফেরত আনবে) — list_file_change_history দিয়ে ইতিহাস দেখা যায়।",
        "পাসওয়ার্ড/OTP/পেমেন্ট-তথ্যের মতো স্পর্শকাতর কিছু type_text দিয়ে টাইপ করার আগে বিশেষভাবে সতর্ক "
        "থাকো এবং সম্ভব হলে ইউজারকে নিশ্চিত করতে বলো।",
        "মাউস/কীবোর্ড টুল কাজ না করলে (Wayland/no-display) সেটা স্পষ্টভাবে ইউজারকে বলো, বিকল্প (ydotool/X11) বলে দাও।",
        "সিস্টেমের ক্ষতি হতে পারে এমন কমান্ড (rm -rf, format, ইত্যাদি) approval-এ স্পষ্টভাবে ঝুঁকি উল্লেখ করো।",
    ],
    markdown=True,
    **MEMORY_KWARGS,
)
