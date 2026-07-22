"""
config.py
=========
মডেল সিলেকশন এখন ৩ ধাপে কাজ করে (OpenRouter-এর নিজস্ব fallback ফিচার দিয়ে,
একই রিকোয়েস্টে):
  ধাপ ১ (Fixed)  -> সেই টাস্কের জন্য যেই মডেল ভালো, সেটা প্রথমে ট্রাই হয়
  ধাপ ২ (Free)   -> ধাপ ১ ব্যর্থ/unavailable হলে OpenRouter-এর ফ্রি অটো-রাউটার
  ধাপ ৩ (Paid)   -> ধাপ ২-ও ব্যর্থ হলে (এবং OPENROUTER_MODEL_PAID সেট থাকলে) পেইড মডেল

টাস্ক-টাইপ অনুযায়ী ডিফল্ট ফিক্সড মডেল .env-এ বদলানো যায় (slug মাঝেমধ্যে বদলায়,
openrouter.ai/models-এ গিয়ে যাচাই করে নিও)।

---------------------------------------------------------------------------
অফলাইন/লোকাল মোড (ইন্টারনেট না থাকলেও কাজ চালু রাখতে):
---------------------------------------------------------------------------
`.env`-এ `LOCAL_MODEL_MODE=1` সেট করলে (এবং লোকাল মেশিনে Ollama ইনস্টল+চালু
থাকলে — `ollama serve`, ডিফল্ট `http://localhost:11434`) পুরো সিস্টেম
OpenRouter-এর বদলে সরাসরি লোকাল Ollama মডেল ব্যবহার করবে (`OPENROUTER_API_KEY`
লাগবে না, কোনো ইন্টারনেট লাগবে না মডেল-কলের জন্য)। এটা স্বয়ংক্রিয় hot-fallback
না (মানে চলতি চলতি নেট চলে গেলে মাঝপথে বদলে যাবে না) — এটা একটা explicit মোড,
ইউজার নিজে চালু/বন্ধ করে (env var বদলে + সার্ভার রিস্টার্ট করে)। মডেলের মান
(quality) ক্লাউড মডেলের চেয়ে কম হবে, তবে ছোট/হালকা কাজ + সম্পূর্ণ অফলাইন
নির্ভরযোগ্যতার জন্য এটাই বাস্তবসম্মত সমাধান — সত্যিকারের mid-request fallback
করতে হলে প্রতিটা এজেন্ট-কল try/except-এ মুড়ে দুটো ভিন্ন model client রাখা লাগবে,
যা এই মুহূর্তে করা হয়নি (ভবিষ্যতের কাজ হিসেবে নোট করা রইলো)।

মডেল ডাউনলোড করতে (প্রথমবার ইন্টারনেট লাগবে):
    ollama pull qwen2.5:7b       # সাধারণ কাজের জন্য (ডিফল্ট)
    ollama pull qwen2.5-coder:7b # কোডিং-এর জন্য (ভালো ফল দেয়)
"""

import base64
import json
import logging
import os

import requests
from dotenv import load_dotenv

load_dotenv()

from agno.models.openrouter import OpenRouter
from agno.db.mongo import MongoDb

logger = logging.getLogger("config")

LOCAL_MODEL_MODE = os.getenv("LOCAL_MODEL_MODE", "0") == "1"
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# ---------- Icon/GUI vision (multimodal মডেল দিয়ে টেক্সট-বিহীন বাটন/আইকন খুঁজে বের করা) ----------
# slug মাঝেমধ্যে বদলায় — openrouter.ai/models (ফিল্টার: modality "image->text", price "free")
# -এ গিয়ে যাচাই করে নিও, বদলে গেলে .env-এ OPENROUTER_MODEL_VISION বসিয়ে ওভাররাইড করো।
OPENROUTER_MODEL_VISION = os.getenv("OPENROUTER_MODEL_VISION", "qwen/qwen2.5-vl-32b-instruct:free")
# লোকাল মোডে (LOCAL_MODEL_MODE=1) Ollama vision মডেল — আগে টেনে রাখতে হবে: `ollama pull llava`
OLLAMA_MODEL_VISION = os.getenv("OLLAMA_MODEL_VISION", "llava")

# ---------- টাস্ক-ভিত্তিক লোকাল (Ollama) মডেল — LOCAL_MODEL_MODE=1 হলে ব্যবহৃত হয় ----------
LOCAL_TASK_MODEL_DEFAULTS = {
    "coding":    os.getenv("OLLAMA_MODEL_CODING", "qwen2.5-coder:7b"),
    "reasoning": os.getenv("OLLAMA_MODEL_REASONING", "qwen2.5:7b"),
    "research":  os.getenv("OLLAMA_MODEL_RESEARCH", "qwen2.5:7b"),
    "creative":  os.getenv("OLLAMA_MODEL_CREATIVE", "qwen2.5:7b"),
    "social":    os.getenv("OLLAMA_MODEL_SOCIAL", "qwen2.5:7b"),
    "general":   os.getenv("OLLAMA_MODEL_GENERAL", "qwen2.5:7b"),
}

# ---------- টাস্ক-ভিত্তিক ফিক্সড মডেল (ধাপ ১, ক্লাউড/OpenRouter মোড) ----------
TASK_MODEL_DEFAULTS = {
    "coding":    os.getenv("OPENROUTER_MODEL_CODING", "qwen/qwen3-coder:free"),
    "reasoning": os.getenv("OPENROUTER_MODEL_REASONING", "deepseek/deepseek-r1:free"),
    "research":  os.getenv("OPENROUTER_MODEL_RESEARCH", "deepseek/deepseek-chat-v3.1:free"),
    "creative":  os.getenv("OPENROUTER_MODEL_CREATIVE", "meta-llama/llama-3.3-70b-instruct:free"),
    "social":    os.getenv("OPENROUTER_MODEL_SOCIAL", "meta-llama/llama-3.3-70b-instruct:free"),
    "general":   os.getenv("OPENROUTER_MODEL_FREE", "openrouter/free"),
}


def _build_openrouter(model_id: str, api_key: str, fallback_ids: list):
    """
    fallback_ids থাকলে OpenRouter-এর native fallback (extra_body.models) ব্যবহার করে
    একই রিকোয়েস্টে ধাপ ২/৩ ট্রাই করে। ইনস্টল করা Agno ভার্সনে request_params
    সাপোর্ট না থাকলে (পুরনো ভার্সন) নিরাপদে শুধু primary model দিয়ে চালাবে।
    """
    kwargs = dict(id=model_id, api_key=api_key)
    if fallback_ids:
        kwargs["request_params"] = {"extra_body": {"models": fallback_ids}}
    try:
        return OpenRouter(**kwargs)
    except TypeError:
        return OpenRouter(id=model_id, api_key=api_key)


def _build_local(task: str):
    """LOCAL_MODEL_MODE=1 হলে এই ফাংশন ব্যবহার হয় — সম্পূর্ণ লোকাল Ollama মডেল,
    কোনো ইন্টারনেট/API key ছাড়াই।"""
    try:
        from agno.models.ollama import Ollama
    except ImportError as e:
        raise RuntimeError(
            "LOCAL_MODEL_MODE=1 সেট করা কিন্তু agno-তে Ollama সাপোর্ট পাওয়া যায়নি — "
            "'pip install ollama' করা আছে কিনা যাচাই করো।"
        ) from e
    model_id = LOCAL_TASK_MODEL_DEFAULTS.get(task, LOCAL_TASK_MODEL_DEFAULTS["general"])
    return Ollama(id=model_id, host=OLLAMA_HOST)


def get_model(task: str = "general"):
    """
    task: "coding" | "reasoning" | "research" | "creative" | "social" | "general"
    """
    if LOCAL_MODEL_MODE:
        return _build_local(task)

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY পাওয়া যায়নি। .env ফাইলে বসাও (openrouter.ai থেকে ফ্রি key নেওয়া যায়), "
            "অথবা সম্পূর্ণ অফলাইনে চালাতে .env-এ LOCAL_MODEL_MODE=1 সেট করে লোকাল Ollama ব্যবহার করো "
            "('ollama serve' চালু থাকতে হবে ও অন্তত একটা মডেল pull করা থাকতে হবে)।"
        )

    primary = TASK_MODEL_DEFAULTS.get(task, TASK_MODEL_DEFAULTS["general"])
    free_router = os.getenv("OPENROUTER_MODEL_FREE", "openrouter/free")
    paid = os.getenv("OPENROUTER_MODEL_PAID")  # খালি রাখলে ধাপ ৩ স্কিপ হবে

    chain = []
    for m in (primary, free_router, paid):
        if m and m not in chain:
            chain.append(m)

    if not paid:
        print(
            f"ℹ️  [{task}] টাস্কে পেইড ফলব্যাক (OPENROUTER_MODEL_PAID) সেট করা নেই — "
            f"ফিক্সড ও ফ্রি দুটোই ব্যর্থ হলে এই টাস্কে এরর আসবে। .env-এ বসালে ৩য় ধাপ চালু হবে।"
        )

    return _build_openrouter(model_id=chain[0], api_key=api_key, fallback_ids=chain[1:])


def get_db():
    """সব agent/team-এর session+memory MongoDB-তে persist হয়।"""
    db_url = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    return MongoDb(db_url=db_url, db_name=os.getenv("MONGODB_DB_NAME", "agno_system"))


# ---------- মেমরি সেটিংস — প্রতিটা Agent/Team তৈরির সময় **MEMORY_KWARGS দিয়ে দাও ----------
MEMORY_KWARGS = dict(
    add_history_to_context=True,   # আগের কথোপকথন প্রতিবার context-এ যোগ হবে
    num_history_runs=10,            # সর্বশেষ কত turn মনে রাখবে
    enable_agentic_memory=True,     # ইউজার সম্পর্কে দরকারি তথ্য নিজে থেকে মনে রাখবে (agno_memories)
)


def ask_text_model(prompt: str, task: str = "reasoning", max_tokens: int = 800, timeout: int = 60) -> dict:
    """একটা স্টেটলেস টেক্সট-শুধু প্রম্পট মডেলকে পাঠিয়ে উত্তর আনে (ছবি ছাড়া) — HTTP দিয়ে
    সরাসরি, পূর্ণ agno Agent/session/memory ওভারহেড ছাড়া। memory_core.py এটা ব্যবহার করে
    পুরনো কথোপকথন সংক্ষিপ্ত করতে (একটা ব্যাচ-জব, কোনো নির্দিষ্ট Agent-এর কাজ না)।

    Args:
        prompt: মডেলকে যা জিজ্ঞেস করা হবে
        task: TASK_MODEL_DEFAULTS/LOCAL_TASK_MODEL_DEFAULTS-এর কোন ফিক্সড মডেল ব্যবহার হবে
        max_tokens: রেসপন্সের সর্বোচ্চ টোকেন
        timeout: HTTP রিকোয়েস্ট টাইমআউট (সেকেন্ড)
    """
    if LOCAL_MODEL_MODE:
        model_id = LOCAL_TASK_MODEL_DEFAULTS.get(task, LOCAL_TASK_MODEL_DEFAULTS["general"])
        try:
            resp = requests.post(
                f"{OLLAMA_HOST}/api/chat",
                json={"model": model_id, "messages": [{"role": "user", "content": prompt}], "stream": False},
                timeout=timeout,
            )
            resp.raise_for_status()
            text = (resp.json().get("message") or {}).get("content", "")
            if not text:
                return {"status": "error", "error": f"Ollama মডেল ({model_id}) থেকে খালি উত্তর।"}
            return {"status": "ok", "text": text}
        except requests.exceptions.ConnectionError:
            return {"status": "error", "error": f"Ollama-এ কানেক্ট করা যায়নি ({OLLAMA_HOST}) — 'ollama serve' চালু আছে কিনা যাচাই করো।"}
        except Exception as e:  # noqa: BLE001
            return {"status": "error", "error": f"Ollama কল ব্যর্থ: {e}"}

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return {"status": "error", "error": "OPENROUTER_API_KEY নেই — .env-এ বসাও, অথবা LOCAL_MODEL_MODE=1 সেট করো।"}
    model_id = TASK_MODEL_DEFAULTS.get(task, TASK_MODEL_DEFAULTS["general"])
    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model_id, "max_tokens": max_tokens,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=timeout,
        )
        if resp.status_code != 200:
            return {"status": "error", "error": f"OpenRouter কল ব্যর্থ (HTTP {resp.status_code}): {resp.text[:300]}"}
        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            return {"status": "error", "error": f"OpenRouter থেকে খালি উত্তর: {json.dumps(data, ensure_ascii=False)[:300]}"}
        return {"status": "ok", "text": choices[0]["message"]["content"]}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "error": f"OpenRouter-এ নেটওয়ার্ক সমস্যা: {e}"}
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "error": f"OpenRouter কল ব্যর্থ: {e}"}


def ask_vision_model(image_path: str, prompt: str, max_tokens: int = 700, timeout: int = 60) -> dict:
    """একটা ছবি + প্রম্পট একটা multimodal (vision) মডেলকে পাঠিয়ে টেক্সট রেসপন্স আনে।
    এটা agno Agent ফ্রেমওয়ার্ক দিয়ে না, সরাসরি HTTP কল দিয়ে করা হয় — কারণ এটা একবারের
    "এই ছবিতে X কোথায়" জাতীয় স্টেটলেস প্রশ্ন, পূর্ণ Agent/session/memory ওভারহেড লাগে না।

    LOCAL_MODEL_MODE=1 হলে লোকাল Ollama vision মডেল (OLLAMA_MODEL_VISION) ব্যবহার হয়,
    নাহলে OpenRouter (OPENROUTER_MODEL_VISION) — উভয় ক্ষেত্রেই ব্যর্থ হলে exception না
    ছুঁড়ে একটা স্পষ্ট dict রিটার্ন করে, যাতে কলিং কোড (vision_agent.locate_icon) সেটা
    সরাসরি ইউজারকে বলে দিতে পারে।

    Args:
        image_path: লোকাল ফাইলে সেভ করা ছবির পাথ (PNG/JPEG)
        prompt: মডেলকে যা জিজ্ঞেস করা হবে
        max_tokens: রেসপন্সের সর্বোচ্চ টোকেন
        timeout: HTTP রিকোয়েস্ট টাইমআউট (সেকেন্ড) — vision মডেল সাধারণত ধীর, তাই ডিফল্ট বেশি রাখা হয়েছে
    """
    try:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "error": f"ছবি পড়া যায়নি ({image_path}): {e}"}

    if LOCAL_MODEL_MODE:
        try:
            resp = requests.post(
                f"{OLLAMA_HOST}/api/chat",
                json={
                    "model": OLLAMA_MODEL_VISION,
                    "messages": [{"role": "user", "content": prompt, "images": [b64]}],
                    "stream": False,
                },
                timeout=timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            text = (data.get("message") or {}).get("content", "")
            if not text:
                return {"status": "error", "error": f"Ollama vision মডেল ({OLLAMA_MODEL_VISION}) থেকে খালি উত্তর — মডেলটা 'ollama pull {OLLAMA_MODEL_VISION}' দিয়ে টানা আছে কিনা যাচাই করো।"}
            return {"status": "ok", "text": text}
        except requests.exceptions.ConnectionError:
            return {"status": "error", "error": f"Ollama-এ কানেক্ট করা যায়নি ({OLLAMA_HOST}) — 'ollama serve' চালু আছে কিনা যাচাই করো।"}
        except Exception as e:  # noqa: BLE001
            return {"status": "error", "error": f"Ollama vision কল ব্যর্থ: {e} — 'ollama pull {OLLAMA_MODEL_VISION}' করা আছে কিনা যাচাই করো।"}

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return {"status": "error", "error": "OPENROUTER_API_KEY নেই — .env-এ বসাও, অথবা সম্পূর্ণ অফলাইনে চালাতে LOCAL_MODEL_MODE=1 সেট করো।"}
    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": OPENROUTER_MODEL_VISION,
                "max_tokens": max_tokens,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    ],
                }],
            },
            timeout=timeout,
        )
        if resp.status_code != 200:
            return {"status": "error", "error": f"OpenRouter vision কল ব্যর্থ (HTTP {resp.status_code}): {resp.text[:300]} — মডেল স্লাগ '{OPENROUTER_MODEL_VISION}' এখনো আছে কিনা openrouter.ai/models-এ যাচাই করো।"}
        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            return {"status": "error", "error": f"OpenRouter থেকে খালি উত্তর: {json.dumps(data, ensure_ascii=False)[:300]}"}
        text = choices[0]["message"]["content"]
        return {"status": "ok", "text": text}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "error": f"OpenRouter-এ নেটওয়ার্ক সমস্যা: {e}"}
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "error": f"OpenRouter vision কল ব্যর্থ: {e}"}


def has_key(*env_vars: str) -> bool:
    """কোনো টুল/agent activate করার আগে দরকারি key(s) সেট আছে কিনা চেক করার হেল্পার।
    key না থাকলে True/False রিটার্ন করে — agent ফাইলে এটা দিয়ে conditional import করা হয়,
    ফলে key ছাড়া পুরো সিস্টেম ক্র্যাশ করে না, শুধু ওই টুলটা বাদ পড়ে ও warning দেখায়।"""
    return all(os.getenv(v) for v in env_vars)
