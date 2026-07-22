# Agno General-Purpose Supervisor System

## আর্কিটেকচার

```
Supervisor (Team, mode=coordinate) — teams/registry.py দিয়ে অটো-লোড হয়
├── Knowledge Team           — Research / Data / Finance Agent
├── Operations Team          — Communication / Productivity / Media Agent
├── Automation Team          — Browser Agent
├── Coding Team              — Coding Agent (হেভি-ডিউটি: ফাইল/শেল/পাইথন/Docker/GitHub/GitLab/সন্ডবক্স)
├── Social Media Team        — Facebook / TikTok / YouTube / Telegram / Other(X,Reddit,Discord,WhatsApp) Agent
├── E-commerce Team          — E-commerce Agent (Shopify/WooCommerce/ইত্যাদি)
├── PC Team                  — PC Agent (OS-লেভেল অটোমেশন)
├── Vision Team              — Vision Agent (স্ক্রিনশট + OCR — perception layer)
├── Voice Team               — Voice Agent (ডিভাইস স্পিকারে সরাসরি বলা)
├── Scheduler Team           — Scheduler Agent (proactive/রিমাইন্ডার/cron — APScheduler)
├── Security Team            — Security Agent (approval-gate + encrypted vault)
├── Personal Knowledge Team  — Personal Knowledge Agent (নিজস্ব নোট/ডকুমেন্ট RAG)
├── IoT Team                 — IoT Agent (Home Assistant দিয়ে স্মার্ট হোম)
├── Media Generation Team    — Media Generation Agent (ছবি/ভিডিও তৈরি)
├── Meta Team                — Meta Agent (self-extension — নতুন Team/Agent লেখে)
├── Notification Team        — Notification Agent (Linux ডেস্কটপ নোটিফিকেশন)
└── Linux System Team        — Linux System Agent (প্যাকেজ ইনস্টল/রিমুভ/আপডেট + systemd সার্ভিস কন্ট্রোল)
```

**নোট:** এই প্রজেক্ট এখন ইচ্ছাকৃতভাবে **শুধু Linux**-কেন্দ্রিক — Windows/Android
ডিপ্লয়মেন্ট ও Mobile (ADB) কন্ট্রোল সরিয়ে ফেলা হয়েছে যাতে একটামাত্র প্ল্যাটফর্মে
(এই ISO যেই Linux মেশিনে চলবে) পুরো ফোকাস দেওয়া যায়।

## Linux System Team (`linux_tools.py` + `privilege.py`)

`apt`/`dnf`/`pacman`/`zypper`/`apk` — distro `/etc/os-release` দেখে অটো-ডিটেক্ট হয়,
নতুন প্যাকেজ-ম্যানেজার যোগ করতে চাইলে `linux_tools.py`-র `PACKAGE_MANAGERS`
ডিকশনারিতে একটা এন্ট্রি বসালেই হয় (নতুন if-branch লিখতে হয় না)।

- `install_package` / `remove_package` / `update_system` — প্রতিটাই **ভেতরে
  বাধ্যতামূলক human-approval** নেয় (guardrail.py), এজেন্ট এটা এড়িয়ে যেতে পারে না।
- `control_service` (start/stop/restart/enable/disable) — approval লাগে, আর
  ssh/network/dbus/systemd-core/এই সিস্টেম নিজে **কোড-লেভেলে হার্ড-ব্লকড** —
  approval দিলেও টাচ করা যায় না (ভুলে নিজেকে লকআউট ঠেকাতে)।
- প্রতিটা কমান্ডের ফলাফল JSON (status/returncode/stdout/stderr) আকারে আসে —
  ডিবাগ করা সহজ, এজেন্ট আর মানুষ দুজনেই ঠিক কী হলো দেখতে পারে।
- root-প্রিভিলেজ লাগলে `privilege.py` `sudo -n` (নন-ইন্টারঅ্যাক্টিভ) দিয়ে চালায় —
  পাসওয়ার্ডহীন sudo সেট না থাকলে **হ্যাং না করে সাথে সাথে স্পষ্ট এরর মেসেজ** দেয়।

## install.sh — এক-কমান্ড ইনস্টলার (Linux)

```bash
bash install.sh
```

কী করে (প্রতিটা ধাপ idempotent — বারবার চালালেও সমস্যা হয় না):
1. distro/প্যাকেজ-ম্যানেজার ডিটেক্ট করে
2. python3-venv, ffmpeg, tesseract-ocr ইনস্টল করে (আগে জিজ্ঞেস করে)
3. venv বানিয়ে `requirements.txt` ইনস্টল করে
4. `.env.example` থেকে `.env` তৈরি করে (আগে থেকে থাকলে ছোঁয় না)
5. Docker থাকলে MongoDB কন্টেইনার চালু করে (আগে জিজ্ঞেস করে)
6. **sudoers.d এন্ট্রি বসায়** — শুধু প্যাকেজ-ম্যানেজার বাইনারি ও `systemctl`-এর
   নির্দিষ্ট অ্যাকশনের জন্য পাসওয়ার্ডহীন sudo (`ALL=(ALL) NOPASSWD: ALL` না!);
   বসানোর আগে `visudo -c` দিয়ে সিনট্যাক্স-যাচাই বাধ্যতামূলক — ভুল হলে কিছুই বসে না
7. systemd সার্ভিস বসিয়ে বুটে অটো-স্টার্ট চালু করে
   (`deploy/linux/agno-system.service.template` থেকে পাথ বসিয়ে জেনারেট হয়)

`set -euo pipefail` + লাইন-নম্বরসহ ERR trap থাকায় যেকোনো ধাপ ব্যর্থ হলে স্ক্রিপ্ট
সাথে সাথে থামবে এবং ঠিক কোথায় সমস্যা হলো বলবে — নীরবে অর্ধেক-ইনস্টল অবস্থায় রাখবে না।

## Guardrail / Approval-gate (safety layer)

`guardrail.py`-তে একটা approval-broker আছে। ঝুঁকিপূর্ণ/অপরিবর্তনীয় কাজ করা এজেন্ট
(PC, Coding, E-commerce, Facebook, IoT, Meta) কাজের আগে `request_approval`
টুল কল করে — ততক্ষণ agent ব্লক থাকে যতক্ষণ না UI-র approval panel (নিচে-ডানে) থেকে
ইউজার Approve/Deny করে (ডিফল্ট ৫ মিনিট টাইমআউট, তারপর auto-deny)। সব approval
request `agno_approvals` কালেকশনে audit log হিসেবে থাকে। `wait_for_approval_async`
ব্যবহার করা হয় যাতে অপেক্ষার সময় (asyncio.to_thread দিয়ে) পুরো সার্ভার/অন্য
সেশনগুলো ফ্রিজ না হয়।

**`safety_tools.py` — কোডে-এনফোর্সড ফাইল/শেল নিরাপত্তা:** PC Agent ও Coding
Agent-এ raw agno `ShellTools`/`FileTools` সরাসরি দেওয়া হয় না (ওগুলোর approval
শুধু prompt-instruction-নির্ভর ছিল, কোডে enforce করা ছিল না)। এর বদলে
`SafeShellTools`/`SafeFileTools` ব্যবহার হয়:
- প্রতিটা শেল কমান্ড ও ফাইল write/append/delete কোডেই বাধ্যতামূলক approval-gate
  পার হয় (fail-closed — guardrail লোড না হলেও deny)।
- ফাইল ওভাররাইট/ডিলিটের ঠিক আগে `.snapshots/`-এ স্বয়ংক্রিয় ব্যাকআপ নেওয়া হয়;
  `undo_last_file_change` দিয়ে সবচেয়ে সাম্প্রতিক পরিবর্তন ফেরানো যায়,
  `list_file_change_history` দিয়ে ইতিহাস দেখা যায়।
- read/list-এর মতো নিরাপদ অপারেশনে approval লাগে না, নাহলে সিস্টেম অব্যবহারযোগ্য
  হয়ে যেত।

(সিস্টেম-লেভেল ভারী অ্যাকশনের জন্য — প্যাকেজ ইনস্টল/রিমুভ, systemd সার্ভিস
কন্ট্রোল — `linux_tools.py` আলাদাভাবে `snapshot.py`-র মাধ্যমে Timeshift
রিস্টোর-পয়েন্ট নেয়, নিচে দেখো।)

## Proactive/Scheduler layer

`scheduler.py`-তে APScheduler (MongoDB job-store দিয়ে, তাই রিস্টার্টেও হারায় না)
ব্যবহার করে "AI নিজে থেকে কাজ করা" চালু করা হয়েছে — Scheduler Agent দিয়ে এক-বারের
বা cron-ভিত্তিক পুনরাবৃত্ত টাস্ক তৈরি করা যায়। জব ফায়ার হলে সেই prompt supervisor-কে
পাঠানো হয়, ফলাফল `agno_scheduler_results`-এ লগ হয় এবং সম্ভব হলে ডেস্কটপ নোটিফিকেশন যায়।
FastAPI স্টার্টআপেই (`server.py`) এই scheduler চালু হয়ে যায়।

## Observability

প্রতিটা চ্যাট-এক্সচেঞ্জ (`server.py`) `agno_traces` কালেকশনে লগ হয় — session_id,
মেসেজ, কোন কোন টিম উত্তর দিল, উত্তরের দৈর্ঘ্য। এখন একটা লাইভ **ড্যাশবোর্ড**ও আছে:
`http://localhost:8000/dashboard` — সাম্প্রতিক চ্যাট-ট্রেস, শিডিউল করা কাজের ফলাফল,
আর approval history (audit log) একসাথে দেখা যায়, প্রতি ৫ সেকেন্ডে অটো-রিফ্রেশ হয়।

## ডেস্কটপ কন্ট্রোল — "মানুষ যা করতে পারে" (`desktop_control.py`)

PC Agent এখন `DesktopControlTools` দিয়ে সরাসরি ডেস্কটপ নিয়ন্ত্রণ করতে পারে:
- **মাউস/কীবোর্ড**: `move_and_click`, `type_text`, `press_key` (xdotool প্রাধান্য, না থাকলে pyautogui fallback)
- **উইন্ডো ম্যানেজমেন্ট**: `list_windows`, `focus_window`, `close_window` (wmctrl)
- **ক্লিপবোর্ড**: `get_clipboard`, `set_clipboard` (xclip/xsel)
- **অ্যাপ চালু করা**: `launch_application` (approval-gated)

X11-এ পুরোপুরি কাজ করে; **Wayland**-এ সিকিউরিটি মডেলের কারণে xdotool/pyautogui
সীমিত — কোড এটা ডিটেক্ট করে স্পষ্ট এরর দেয় (চুপচাপ ব্যর্থ হয় না), বিকল্প হিসেবে
`ydotool` সাজেস্ট করে। মাউস/কীবোর্ডের প্রতি মাইক্রো-অ্যাকশনে approval নেই (তাহলে
অব্যবহারযোগ্য হয়ে যাবে) — শুধু windows বন্ধ করা ও app চালু করার মতো state-changing
অ্যাকশনে approval লাগে।

## Voice Daemon — Always-listening / Wake-word (`voice_daemon.py`)

সত্যিকারের "Jarvis" অভিজ্ঞতা: মাইক্রোফোনে সবসময় কান পেতে থাকে, wake word
("Hey Agno" / "জার্ভিস", `.env`-এর `WAKE_WORDS`-এ কাস্টমাইজযোগ্য) শুনলে পরের
কথাটা কমান্ড হিসেবে ধরে `/api/chat`-এ পাঠায়, উত্তর `/api/tts` দিয়ে স্পিকারে বলে।
আলাদা প্রসেস/সার্ভিস হিসেবে চলে (server.py-র বাইরে) কারণ Whisper CPU-ভারী ও
মাইক-লুপ ব্লকিং।

- ম্যানুয়াল রান: `./venv/bin/python voice_daemon.py`
- systemd সার্ভিস (ঐচ্ছিক, ডিফল্টে বন্ধ): `install.sh`-এর শেষ ধাপে অথবা ম্যানুয়ালি
  `deploy/linux/agno-voice.service.template` দিয়ে
- `WHISPER_MODEL_SIZE=tiny` ডিফল্ট (দ্রুত, কম রিসোর্স) — নির্ভুলতা বেশি লাগলে
  `base`/`small`-এ বদলানো যায় (.env), তবে CPU খরচ বাড়বে

## polkit — sudoers-এর বিকল্প (`polkit/`, `scripts/install_polkit.sh`)

`install.sh` ডিফল্টে sudoers.d ব্যবহার করে। যারা polkit-centric সেটআপ (Fedora
Workstation-টাইপ) পছন্দ করেন, তাদের জন্য বিকল্প: `bash scripts/install_polkit.sh`
— শুধু systemd সার্ভিস কন্ট্রোলের জন্য (প্যাকেজ ম্যানেজার এখনো sudoers-নির্ভর,
কারণ apt/dnf/pacman-এর কোনো স্ট্যান্ডার্ড polkit action-id নেই)। বিস্তারিত:
`polkit/README.md`।

## PWA (ইনস্টলযোগ্য অ্যাপ)

`static/manifest.json`-এ এখন আইকন (`icon.svg`) আছে এবং `static/sw.js` (service
worker) app-shell অফলাইন cache করে — ব্রাউজারে "Add to Home Screen"/"Install App"
দিয়ে ডেস্কটপ/মোবাইলে নেটিভ অ্যাপের মতো ইনস্টল করা যায় (চ্যাট/API কল ইন্টারনেট/লোকাল
সার্ভার ছাড়া কাজ করবে না — ইচ্ছাকৃতভাবে শুধু শেল ক্যাশ করা হয়েছে)।

## AI OS হিসেবে ডিপ্লয় করা (শুধু Linux)

`deploy/linux/` ফোল্ডারে systemd ডেমন-সেটআপ আছে:
- `agno-system.service.template` (মূল সার্ভার) + `agno-voice.service.template`
  (ঐচ্ছিক voice daemon) — `install.sh` দুটোই ইন্টারঅ্যাক্টিভভাবে বসাতে পারে।

এই প্রজেক্ট ইচ্ছাকৃতভাবে শুধু একটা Linux মেশিনে (এই ISO/single-machine ইনস্টল)
পুরোপুরি কাজ করার উপর ফোকাস করে — Windows/Android সাপোর্ট বাদ দেওয়া হয়েছে
যাতে একটা প্ল্যাটফর্মেই সবকিছু (শেল, ফাইল, ডেস্কটপ কন্ট্রোল, প্যাকেজ/সার্ভিস
ম্যানেজমেন্ট, ভয়েস, নোটিফিকেশন) সম্পূর্ণ ও নির্ভরযোগ্যভাবে কাজ করে।

## মডেল স্ট্র্যাটেজি (OpenRouter, ৩ ধাপ, এক রিকোয়েস্টেই)

1. **Fixed** — টাস্ক-টাইপ (coding/research/reasoning/creative/social) অনুযায়ী নির্দিষ্ট মডেল
2. **Free** — ধাপ ১ ব্যর্থ হলে OpenRouter-এর `openrouter/free` অটো-রাউটার
3. **Paid** — ধাপ ২-ও ব্যর্থ হলে (এবং `.env`-এ `OPENROUTER_MODEL_PAID` সেট থাকলে) পেইড মডেল

এই পুরো চেইনটা OpenRouter নিজেই একটা রিকোয়েস্টে হ্যান্ডল করে (`config.py`-র
`_build_openrouter` ফাংশন দেখো)। টাস্ক-ভিত্তিক ডিফল্ট মডেল/paid fallback
`.env`-এ বদলানো যায়।

## Key-নির্ভর টুলের নিয়ম

প্রতিটা paid/key-required টুল `has_key(...)` দিয়ে conditional import হয়:
- key থাকলে -> টুল লোড হয়, agent সেটা ব্যবহার করতে পারে
- key না থাকলে -> টুল বাদ পড়ে, কনসোলে ⚠️ warning প্রিন্ট হয় (কোন key লাগবে বলে দেয়),
  কিন্তু **সিস্টেম ক্র্যাশ করে না** — সেই agent শুধু ওই কাজটা করতে পারবে না, বাকি সব চলবে।

## মেমরি

`config.py`-র `MEMORY_KWARGS` প্রতিটা Agent/Team-এ যোগ করা আছে:
- `add_history_to_context` — আগের কথোপকথন মনে রাখে
- `enable_agentic_memory` — ইউজার সম্পর্কে গুরুত্বপূর্ণ তথ্য নিজে থেকে মনে রাখে
- সব MongoDB-তে persist হয়, তাই session বন্ধ করে আবার খুললেও context থাকে

## নতুন টিম যোগ করা (Auto-registration)

`teams/` ফোল্ডারে একটা নতুন `.py` ফাইল বানাও, ভেতরে অবশ্যই `team = Team(...)`
নামের ভ্যারিয়েবল রাখো — ব্যাস, `supervisor.py`-তে কিছু বদলাতে হবে না,
`teams/registry.py` নিজে থেকেই সেটা লোড করে নেবে।

```python
# teams/my_new_team.py
from agno.team.team import Team
from config import get_model, get_db, MEMORY_KWARGS
from agents.my_agent import my_agent

team = Team(
    name="My New Team",
    mode="coordinate",
    model=get_model("general"),
    db=get_db(),
    members=[my_agent],
    instructions=["..."],
    **MEMORY_KWARGS,
)
```

## সেটআপ

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# .env-এ অন্তত OPENROUTER_API_KEY আর MONGODB_URI বসাও

docker run -d --name local-mongo -p 27017:27017 mongo   # লোকাল MongoDB না থাকলে

python main.py
```

## সততার সাথে সীমাবদ্ধতা

- **Facebook/Instagram/TikTok**: Agno-তে রেডিমেড টুলকিট নেই। এজেন্টদের
  PythonTools দেওয়া আছে, তারা নিজেরাই Graph API/TikTok Business API কল
  করবে — কিন্তু access token পেতে Meta/TikTok-এর নিজস্ব app review ও
  business verification লাগবে, এটা শুধু `.env`-এ key বসানোর চেয়ে বেশি কিছু।
- **Desktop Control**: X11-এ ভালো কাজ করে (xdotool/wmctrl), কিন্তু **Wayland**-এ
  সীমিত — Wayland ইচ্ছাকৃতভাবে গ্লোবাল ইনপুট-ইনজেকশন আটকায় (নিরাপত্তার জন্য),
  তাই সেখানে `ydotool` বা X11 সেশনে ফিরে যাওয়া লাগবে। `locate_text`/`click_text`
  (OCR bounding-box ভিত্তিক) দিয়ে টেক্সট/বাটন-লেবেল দেখে ক্লিক করা যায়, কিন্তু
  এটা এখনো OCR-নির্ভর — টেক্সট-বিহীন আইকন-শুধু বাটনে কাজ করে না (একটা সত্যিকারের
  মাল্টিমোডাল vision-grounding মডেল হলে এই সীমাবদ্ধতা কাটত)।
- **Voice Daemon**: `tiny` Whisper মডেল দ্রুত কিন্তু নির্ভুলতা মাঝারি (বিশেষত
  আশেপাশে শব্দ থাকলে ভুল wake-word ডিটেকশন হতে পারে), আর প্রতি ৪ সেকেন্ডে
  একটা করে অডিও-চাংক ট্রান্সক্রাইব করে বলে সত্যিকারের low-power/instant
  wake-word ইঞ্জিন (Porcupine-টাইপ) থেকে কিছুটা ধীর ও বেশি CPU খরচ করে।
- **ফ্রি মডেল/টুলের rate limit** থাকে — ভারী কাজে মাঝেমধ্যে ধাপ ৩ (পেইড)
  ফলব্যাক দরকার হতে পারে, সেজন্য `OPENROUTER_MODEL_PAID` সেট রাখা ভালো।
- **Personal Knowledge Agent** এখন কীওয়ার্ড-ভিত্তিক সার্চ করে, semantic/vector
  RAG না — বড় ডকুমেন্ট সংগ্রহে কিছু প্রাসঙ্গিক তথ্য মিস হতে পারে।
- **Approval-gate (guardrail.py)** single-process in-memory ব্লকিং ব্যবহার করে —
  একাধিক uvicorn worker/process দিয়ে চালালে কাজ করবে না (তখন Redis-ভিত্তিক
  broker-এ আপগ্রেড করা লাগবে)।
- **polkit বিকল্প** শুধু systemd সার্ভিস কন্ট্রোল কভার করে, প্যাকেজ ম্যানেজার না —
  সেটা এখনো sudoers.d-নির্ভর।
- **Vision Agent** শুধু GUI/ডিসপ্লে থাকা মেশিনে কাজ করে, হেডলেস সার্ভারে না।
- **Meta Agent** নতুন ফাইল লিখলেও চলমান প্রসেসে সাথে সাথে লোড হয় না —
  registry.py আবার স্ক্যান করতে সার্ভার রিস্টার্ট লাগবে।
