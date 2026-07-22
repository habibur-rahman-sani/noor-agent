"""
safety_tools.py
================
agno-র raw `ShellTools`/`FileTools` সরাসরি এজেন্টকে দিলে সমস্যা: ওগুলোর
কোনো approval-gate বা backup/undo বিল্ট-ইন নেই — এজেন্টের instructions-এ
"approval নাও" লেখা থাকলেও সেটা শুধু একটা অনুরোধ, মডেল ভুলে গেলে বা
কনফিউজড হলে সরাসরি ফাইল ডিলিট/ওভাররাইট বা শেল কমান্ড চালিয়ে ফেলতে পারে।

এই মডিউল সেই ফাঁকটা বন্ধ করে — কোডে (prompt-এ না) enforce করা:

1. **Fail-closed approval**: destructive/risky অ্যাকশন (write/delete file,
   shell command) কোডেই `guardrail.py`-র মাধ্যমে মানুষের অনুমোদন ছাড়া
   এগোতে পারে না — guardrail লোড না হলেও deny (approval-gate নিজেই bypass
   করা যায় না, agent যাই বলুক না কেন)।
2. **Backup-before-destroy + undo**: কোনো ফাইল ডিলিট বা ওভাররাইট করার আগে
   তার একটা টাইমস্ট্যাম্পড কপি `.snapshots/`-এ রাখা হয়, আর
   `undo_last_file_change()` দিয়ে সবচেয়ে সাম্প্রতিক পরিবর্তন ফিরিয়ে আনা যায়।
   এভাবে এজেন্ট ভুল করলেও ক্ষতি পূরণযোগ্য থাকে।
3. Read-only অপারেশন (read/list/search) কোনো approval ছাড়াই চলে — প্রতি
   পদক্ষেপে approval চাইলে সিস্টেম ব্যবহারযোগ্য থাকবে না।
"""

import json
import logging
import os
import pathlib
import shutil
import subprocess
import threading
import time

from agno.tools.toolkit import Toolkit

logger = logging.getLogger("safety_tools")

BASE_DIR = pathlib.Path(__file__).parent
SNAPSHOT_DIR = BASE_DIR / ".snapshots"
MANIFEST_PATH = SNAPSHOT_DIR / "manifest.json"
_manifest_lock = threading.Lock()


# ---------------------------------------------------------------- approval --

async def _require_approval(action: str, details: str) -> bool:
    """fail-closed: guardrail লোড/কল ব্যর্থ হলে deny, কখনো fail-open না।"""
    try:
        from guardrail import create_pending_approval, wait_for_approval_async
    except Exception:
        logger.error("guardrail মডিউল লোড করা যায়নি — নিরাপত্তার জন্য অ্যাকশন deny করা হলো।")
        return False
    request_id = create_pending_approval(action, details)
    return await wait_for_approval_async(request_id)


# ---------------------------------------------------------------- snapshot --

def _load_manifest() -> list:
    if not MANIFEST_PATH.exists():
        return []
    try:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_manifest(entries: list) -> None:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


def _snapshot_before_change(target_path: str, action: str) -> str | None:
    """ধ্বংসাত্মক অ্যাকশনের আগে (delete/overwrite) ফাইলের একটা কপি রাখে।
    ফাইলটা আগে থেকেই না থাকলে (নতুন ফাইল তৈরি) কিছু ব্যাকআপ করার নেই, None রিটার্ন করে।
    রিটার্ন করে backup file-এর পাথ, যাতে manifest-এ রাখা যায়।"""
    src = pathlib.Path(target_path)
    if not src.exists() or not src.is_file():
        return None
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup_name = f"{stamp}_{abs(hash(str(src)))}_{src.name}"
    backup_path = SNAPSHOT_DIR / backup_name
    shutil.copy2(src, backup_path)
    with _manifest_lock:
        entries = _load_manifest()
        entries.append({
            "action": action,
            "original_path": str(src.resolve()),
            "backup_path": str(backup_path),
            "at": stamp,
        })
        # সর্বশেষ ৫০টা এন্ট্রি রাখা হয়, পুরনোগুলো (backup ফাইলসহ) মুছে ফেলা হয়
        while len(entries) > 50:
            old = entries.pop(0)
            try:
                pathlib.Path(old["backup_path"]).unlink(missing_ok=True)
            except Exception:
                pass
        _save_manifest(entries)
    return str(backup_path)


def undo_last_change() -> str:
    """সবচেয়ে সাম্প্রতিক ফাইল ডিলিট/ওভাররাইট আনডু করে (ব্যাকআপ থেকে আগের কনটেন্ট
    ফিরিয়ে বসায়)। একাধিকবার কল করলে একের পর এক পুরনো পরিবর্তনগুলো আনডু হবে।"""
    with _manifest_lock:
        entries = _load_manifest()
        if not entries:
            return "আনডু করার মতো কোনো রেকর্ড নেই।"
        entry = entries.pop()
        _save_manifest(entries)
    backup = pathlib.Path(entry["backup_path"])
    original = pathlib.Path(entry["original_path"])
    if not backup.exists():
        return f"ব্যাকআপ ফাইল হারিয়ে গেছে ({backup}) — আনডু করা গেল না।"
    try:
        original.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup, original)
        return f"আনডু সম্পন্ন: '{original}' ফাইলটা '{entry['action']}'-এর আগের অবস্থায় ফিরিয়ে আনা হয়েছে।"
    except Exception as e:  # noqa: BLE001
        return f"আনডু ব্যর্থ: {e}"


def list_undo_history(limit: int = 10) -> str:
    """সাম্প্রতিক ফাইল-পরিবর্তনের তালিকা দেখায় (যেগুলো আনডু করা যাবে)।"""
    entries = _load_manifest()[-limit:][::-1]
    if not entries:
        return "কোনো রেকর্ড নেই।"
    return json.dumps(entries, ensure_ascii=False, indent=2)


# ------------------------------------------------------------------ tools ---

class SafeFileTools(Toolkit):
    """ফাইল read/list করা approval ছাড়াই; write/delete/append approval-gated
    এবং ধ্বংসাত্মক হলে (existing ফাইল ওভাররাইট/ডিলিট) স্বয়ংক্রিয়ভাবে ব্যাকআপ নেয়।"""

    def __init__(self, **kwargs):
        super().__init__(
            name="safe_file_tools",
            tools=[
                self.read_file, self.list_directory, self.write_file,
                self.append_file, self.delete_file, self.undo_last_file_change,
                self.list_file_change_history,
            ],
            **kwargs,
        )

    def read_file(self, path: str) -> str:
        """একটা ফাইলের কনটেন্ট পড়ো (approval লাগে না)।

        Args:
            path: ফাইলের পাথ
        """
        try:
            return pathlib.Path(path).read_text(encoding="utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            return f"পড়া যায়নি: {e}"

    def list_directory(self, path: str = ".") -> str:
        """একটা ফোল্ডারের কনটেন্ট তালিকাবদ্ধ করো (approval লাগে না)।

        Args:
            path: ফোল্ডারের পাথ (ডিফল্ট: বর্তমান ফোল্ডার)
        """
        try:
            items = sorted(os.listdir(path))
            return json.dumps(items, ensure_ascii=False)
        except Exception as e:  # noqa: BLE001
            return f"তালিকা করা যায়নি: {e}"

    async def write_file(self, path: str, content: str) -> str:
        """একটা ফাইলে টেক্সট লেখো (নতুন ফাইল বানায়, অথবা আগে থেকে থাকলে পুরোপুরি
        ওভাররাইট করে — approval লাগবে; ওভাররাইট হলে আগের কনটেন্ট স্বয়ংক্রিয়ভাবে
        ব্যাকআপ হয়ে যায়, `undo_last_file_change` দিয়ে ফেরানো যাবে)।

        Args:
            path: ফাইলের পাথ
            content: ফাইলে যা লেখা হবে
        """
        exists = pathlib.Path(path).exists()
        action = f"ফাইল ওভাররাইট: {path}" if exists else f"নতুন ফাইল তৈরি: {path}"
        if not await _require_approval(action, f"'{path}'-এ {len(content)} ক্যারেক্টার লেখা হবে।"):
            return json.dumps({"status": "denied", "path": path}, ensure_ascii=False)
        if exists:
            _snapshot_before_change(path, "overwrite")
        try:
            p = pathlib.Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return f"'{path}' লেখা হয়েছে।" + (" (আগের ভার্সন ব্যাকআপ হয়েছে, undo করা যাবে)" if exists else "")
        except Exception as e:  # noqa: BLE001
            return f"লেখা যায়নি: {e}"

    async def append_file(self, path: str, content: str) -> str:
        """একটা ফাইলের শেষে টেক্সট যোগ করো (approval লাগবে; ফাইল আগে থেকে থাকলে
        append-এর আগের অবস্থা ব্যাকআপ হয়)।

        Args:
            path: ফাইলের পাথ
            content: যা যোগ করতে হবে
        """
        exists = pathlib.Path(path).exists()
        if not await _require_approval(f"ফাইলে যোগ করা: {path}", f"'{path}'-এর শেষে {len(content)} ক্যারেক্টার যোগ হবে।"):
            return json.dumps({"status": "denied", "path": path}, ensure_ascii=False)
        if exists:
            _snapshot_before_change(path, "append")
        try:
            p = pathlib.Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("a", encoding="utf-8") as f:
                f.write(content)
            return f"'{path}'-এ যোগ করা হয়েছে।"
        except Exception as e:  # noqa: BLE001
            return f"যোগ করা যায়নি: {e}"

    async def delete_file(self, path: str) -> str:
        """একটা ফাইল ডিলিট করো (approval লাগবে; ডিলিটের আগে স্বয়ংক্রিয়ভাবে
        ব্যাকআপ নেওয়া হয়, `undo_last_file_change` দিয়ে ফেরানো যাবে)।

        Args:
            path: যেই ফাইল ডিলিট করতে হবে
        """
        if not pathlib.Path(path).exists():
            return f"'{path}' পাওয়া যায়নি — ডিলিট করার কিছু নেই।"
        if not await _require_approval(f"ফাইল ডিলিট: {path}", f"'{path}' স্থায়ীভাবে ডিলিট করা হবে (ব্যাকআপ রাখা হবে, undo করা যাবে)।"):
            return json.dumps({"status": "denied", "path": path}, ensure_ascii=False)
        _snapshot_before_change(path, "delete")
        try:
            pathlib.Path(path).unlink()
            return f"'{path}' ডিলিট হয়েছে (ব্যাকআপ থেকে undo করা যাবে)।"
        except Exception as e:  # noqa: BLE001
            return f"ডিলিট করা যায়নি: {e}"

    def undo_last_file_change(self) -> str:
        """সবচেয়ে সাম্প্রতিক ফাইল ডিলিট/ওভাররাইট/append আনডু করে — ব্যাকআপ থেকে
        আগের কনটেন্ট ফিরিয়ে বসায়। approval লাগে না (এটা নিজেই একটা সংশোধনমূলক/
        নিরাপদ অ্যাকশন)।"""
        return undo_last_change()

    def list_file_change_history(self, limit: int = 10) -> str:
        """সাম্প্রতিক ফাইল-পরিবর্তনের তালিকা দেখো (কোনটা আনডু করা যাবে বোঝার জন্য)।

        Args:
            limit: সর্বোচ্চ কতগুলো এন্ট্রি দেখাবে
        """
        return list_undo_history(limit)


class SafeShellTools(Toolkit):
    """শেল কমান্ড চালানোর টুল — প্রতিটা কমান্ডের আগে বাধ্যতামূলক approval
    (কোডে enforce করা, prompt-instruction-এর উপর নির্ভর করে না)।"""

    def __init__(self, **kwargs):
        super().__init__(name="safe_shell_tools", tools=[self.run_shell_command], **kwargs)

    async def run_shell_command(self, command: str, timeout: int = 120) -> str:
        """একটা শেল কমান্ড চালাও (pipe/redirect সহ শেল-সিনট্যাক্স সাপোর্ট করে)।
        চালানোর আগে বাধ্যতামূলক human approval লাগে — এটা এড়িয়ে যাওয়ার কোনো
        উপায় নেই, guardrail লোড না হলেও deny হয়ে যায়।

        Args:
            command: চালানোর শেল কমান্ড
            timeout: সেকেন্ডে টাইমআউট (ডিফল্ট ১২০)
        """
        if not await _require_approval("শেল কমান্ড চালানো", f"চালানো হবে: '{command}'"):
            return json.dumps({"status": "denied", "command": command}, ensure_ascii=False)
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=timeout,
            )
            return json.dumps({
                "status": "ok" if result.returncode == 0 else "failed",
                "returncode": result.returncode,
                "stdout": result.stdout[-4000:],
                "stderr": result.stderr[-4000:],
            }, ensure_ascii=False)
        except subprocess.TimeoutExpired:
            return json.dumps({"status": "error", "error": f"{timeout} সেকেন্ডে শেষ হয়নি (timeout)।"}, ensure_ascii=False)
        except Exception as e:  # noqa: BLE001
            return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False)
