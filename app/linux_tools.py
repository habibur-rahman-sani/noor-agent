"""
linux_tools.py
==============
Linux-specific সিস্টেম-ইন্টিগ্রেশন টুল: প্যাকেজ ম্যানেজার (apt/dnf/pacman/zypper/apk)
আর systemd সার্ভিস কন্ট্রোল — কনফিগ-টেবিল-চালিত, যাতে নতুন distro/ম্যানেজার
যোগ করা মানে PACKAGE_MANAGERS ডিকশনারিতে একটা এন্ট্রি বসানো, নতুন if-branch লেখা না।

ডিজাইন সিদ্ধান্ত (ডিবাগ সহজ করার জন্য):
- প্রতিটা টুল-মেথড JSON স্ট্রিং রিটার্ন করে (status/returncode/stdout/stderr সহ) —
  raw স্ট্রিং এর বদলে, যাতে এজেন্ট আর ডেভেলপার দুজনেই ঠিক কী হলো স্পষ্ট দেখতে পারে।
- সব কমান্ড subprocess.run-এ list argv দিয়ে চলে (shell=True কখনোই না) —
  shell-injection ঝুঁকি সম্পূর্ণ বাদ।
- root লাগে এমন অ্যাকশন (install/remove/update, service start/stop/restart/enable/disable)
  টুল-মেথডের **ভেতরেই** বাধ্যতামূলক approval-gate পার হয় — এজেন্ট এটা call করতে
  ভুলে গেলেও বাইপাস হয় না (fail-closed, guardrail লোড না হলেও deny)।
- systemd ইউনিটের একটা ছোট protected-list আছে (ssh/network/dbus/systemd-core/এই
  সিস্টেম নিজে) — approval দিলেও এগুলো control_service দিয়ে টাচ করা যাবে না,
  যাতে ভুলে নিজেকে (বা নেটওয়ার্ক) লকআউট না করে ফেলে।
- approval পাশ হওয়ার পর, আসল কমান্ড চালানোর ঠিক আগে best-effort snapshot.py
  (Timeshift) দিয়ে একটা রিস্টোর-পয়েন্ট নেওয়ার চেষ্টা হয় — এটা রিস্কি অ্যাকশনের
  (install/remove/upgrade/service control) জন্য একটা সেফটি-নেট। Timeshift
  ইনস্টল/কনফিগার করা না থাকলে এটা অ্যাকশন আটকায় না, শুধু ফলাফলে একটা
  "snapshot" ফিল্ডে কী হলো (created/unavailable/unconfigured/failed) জানিয়ে দেয়,
  যাতে ইউজার/এজেন্ট বুঝতে পারে এই অ্যাকশনের রোলব্যাক-সুরক্ষা ছিল কিনা।
"""

import asyncio
import json
import logging
import os
import platform
import re
import shutil
import subprocess

from agno.tools.toolkit import Toolkit

from privilege import build_privileged_command, PrivilegeError

logger = logging.getLogger("linux_tools")

# ---------------------------------------------------------------- config ---
# নতুন distro/প্যাকেজ-ম্যানেজার সাপোর্ট করতে চাইলে শুধু এখানে একটা এন্ট্রি যোগ করো।

PACKAGE_MANAGERS = {
    "apt": {
        "match_ids": {"debian", "ubuntu", "linuxmint", "pop", "raspbian"},
        "binary": "apt-get",
        "install": lambda pkg: ["apt-get", "install", "-y", pkg],
        "remove": lambda pkg: ["apt-get", "remove", "-y", pkg],
        "update": lambda: ["apt-get", "update"],
        "upgrade": lambda: ["apt-get", "upgrade", "-y"],
        "search": lambda pkg: ["apt-cache", "search", pkg],
        "info": lambda pkg: ["apt-cache", "show", pkg],
    },
    "dnf": {
        "match_ids": {"fedora", "rhel", "centos", "rocky", "almalinux"},
        "binary": "dnf",
        "install": lambda pkg: ["dnf", "install", "-y", pkg],
        "remove": lambda pkg: ["dnf", "remove", "-y", pkg],
        "update": lambda: ["dnf", "check-update"],
        "upgrade": lambda: ["dnf", "upgrade", "-y"],
        "search": lambda pkg: ["dnf", "search", pkg],
        "info": lambda pkg: ["dnf", "info", pkg],
    },
    "pacman": {
        "match_ids": {"arch", "manjaro", "endeavouros"},
        "binary": "pacman",
        "install": lambda pkg: ["pacman", "-S", "--noconfirm", pkg],
        "remove": lambda pkg: ["pacman", "-R", "--noconfirm", pkg],
        "update": lambda: ["pacman", "-Sy"],
        "upgrade": lambda: ["pacman", "-Syu", "--noconfirm"],
        "search": lambda pkg: ["pacman", "-Ss", pkg],
        "info": lambda pkg: ["pacman", "-Si", pkg],
    },
    "zypper": {
        "match_ids": {"opensuse", "opensuse-leap", "opensuse-tumbleweed", "sles"},
        "binary": "zypper",
        "install": lambda pkg: ["zypper", "--non-interactive", "install", pkg],
        "remove": lambda pkg: ["zypper", "--non-interactive", "remove", pkg],
        "update": lambda: ["zypper", "refresh"],
        "upgrade": lambda: ["zypper", "--non-interactive", "update"],
        "search": lambda pkg: ["zypper", "search", pkg],
        "info": lambda pkg: ["zypper", "info", pkg],
    },
    "apk": {
        "match_ids": {"alpine"},
        "binary": "apk",
        "install": lambda pkg: ["apk", "add", pkg],
        "remove": lambda pkg: ["apk", "del", pkg],
        "update": lambda: ["apk", "update"],
        "upgrade": lambda: ["apk", "upgrade"],
        "search": lambda pkg: ["apk", "search", pkg],
        "info": lambda pkg: ["apk", "info", pkg],
    },
}

# এই প্যাটার্নে ম্যাচ করা systemd ইউনিট কখনোই control_service দিয়ে টাচ হবে না
# (approval দিলেও না — কোড-লেভেলে হার্ড ব্লক, ভুলে remote lockout ঠেকাতে)
PROTECTED_UNIT_PATTERNS = [
    r"^ssh", r"^network", r"^systemd-", r"^dbus", r"^agno-system",
]


def _read_os_release() -> dict:
    data = {}
    try:
        with open("/etc/os-release", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                data[k] = v.strip('"')
    except FileNotFoundError:
        pass
    return data


def detect_package_manager():
    """প্রথমে /etc/os-release-এর ID/ID_LIKE দিয়ে ম্যাচ করে, না মিললে PATH-এ
    কোন প্যাকেজ-ম্যানেজার বাইনারি আছে সেটা দিয়ে fallback করে।"""
    info = _read_os_release()
    ids = {info.get("ID", "")} | set(info.get("ID_LIKE", "").split())
    for name, spec in PACKAGE_MANAGERS.items():
        if ids & spec["match_ids"]:
            return name
    for name, spec in PACKAGE_MANAGERS.items():
        if shutil.which(spec["binary"]):
            return name
    return None


def _run(argv: list, needs_root: bool, timeout: int = 300) -> dict:
    try:
        final_argv = build_privileged_command(argv) if needs_root else argv
    except PrivilegeError as e:
        return {"status": "error", "error": str(e), "command": " ".join(argv)}

    try:
        result = subprocess.run(final_argv, capture_output=True, text=True, timeout=timeout)
        return {
            "status": "ok" if result.returncode == 0 else "failed",
            "returncode": result.returncode,
            "stdout": result.stdout[-4000:],
            "stderr": result.stderr[-4000:],
            "command": " ".join(final_argv),
        }
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": f"{timeout} সেকেন্ডের মধ্যে শেষ হয়নি (timeout)।",
                "command": " ".join(final_argv)}
    except FileNotFoundError as e:
        return {"status": "error", "error": f"কমান্ড পাওয়া যায়নি: {e}", "command": " ".join(final_argv)}
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "error": str(e), "command": " ".join(final_argv)}


async def _require_approval(action: str, details: str) -> bool:
    """guardrail.py থেকে approval নেয় (async — ব্লকিং অপেক্ষাটা আলাদা থ্রেডে হয়,
    তাই এই কল চলাকালীন সার্ভারের বাকি সেশন আটকায় না)। guardrail ইমপোর্ট/কল
    ব্যর্থ হলে fail-closed (deny) — নিরাপত্তার স্বার্থে fail-open কখনোই না।"""
    try:
        from guardrail import create_pending_approval, wait_for_approval_async
    except Exception:
        logger.error("guardrail মডিউল লোড করা যায়নি — নিরাপত্তার জন্য অ্যাকশন deny করা হলো।")
        return False
    request_id = create_pending_approval(action, details)
    return await wait_for_approval_async(request_id)


async def _snapshot_before(reason: str) -> dict:
    """রিস্কি অ্যাকশনের ঠিক আগে best-effort snapshot নেয়। ব্লকিং subprocess কল
    (কয়েক মিনিট পর্যন্ত লাগতে পারে) আলাদা থ্রেডে চালানো হয় যাতে event loop আটকে না
    থাকে। Timeshift অনুপস্থিত/অকনফিগার্ড হলেও এটা অ্যাকশন আটকায় না — ফলাফল শুধু
    caller-কে জানিয়ে দেয় স্ন্যাপশট আসলে নেওয়া গেছে কিনা।"""
    try:
        from snapshot import create_snapshot
        return await asyncio.to_thread(create_snapshot, reason)
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "message": f"snapshot মডিউল লোড/চালানো যায়নি: {e}"}


# --------------------------------------------------------------- toolkit ---

class PackageManagerTools(Toolkit):
    """distro অটো-ডিটেক্ট করে apt/dnf/pacman/zypper/apk-এর মধ্যে সঠিকটা ব্যবহার
    করে। install/remove/update — এই তিনটার প্রতিটাই ভেতরে বাধ্যতামূলক
    approval-gate পার হয়। search/info শুধু পড়ে, approval লাগে না।"""

    def __init__(self, **kwargs):
        super().__init__(
            name="package_manager_tools",
            tools=[self.detect_system, self.search_package, self.package_info,
                   self.install_package, self.remove_package, self.update_system],
            **kwargs,
        )

    def detect_system(self) -> str:
        """এই মেশিনে কোন distro আর প্যাকেজ ম্যানেজার আছে সেটা বের করো।"""
        manager = detect_package_manager()
        info = _read_os_release()
        return json.dumps({
            "package_manager": manager,
            "distro_name": info.get("PRETTY_NAME") or info.get("NAME") or platform.platform(),
            "supported_managers": list(PACKAGE_MANAGERS.keys()),
        }, ensure_ascii=False)

    def search_package(self, query: str) -> str:
        """প্যাকেজ সার্চ করো (শুধু পড়ে, root/approval লাগে না)।

        Args:
            query: প্যাকেজের নাম বা কীওয়ার্ড
        """
        manager = detect_package_manager()
        if not manager:
            return json.dumps({"status": "error", "error": "সাপোর্টেড প্যাকেজ ম্যানেজার পাওয়া যায়নি।"})
        return json.dumps(_run(PACKAGE_MANAGERS[manager]["search"](query), needs_root=False, timeout=60),
                           ensure_ascii=False)

    def package_info(self, package_name: str) -> str:
        """একটা প্যাকেজ সম্পর্কে বিস্তারিত তথ্য দেখো (ইনস্টলের আগে ভার্সন/সাইজ যাচাইয়ের জন্য ভালো)।

        Args:
            package_name: প্যাকেজের সঠিক নাম
        """
        manager = detect_package_manager()
        if not manager:
            return json.dumps({"status": "error", "error": "সাপোর্টেড প্যাকেজ ম্যানেজার পাওয়া যায়নি।"})
        return json.dumps(_run(PACKAGE_MANAGERS[manager]["info"](package_name), needs_root=False, timeout=30),
                           ensure_ascii=False)

    async def install_package(self, package_name: str) -> str:
        """একটা প্যাকেজ ইনস্টল করো। কল করার সাথে সাথেই ভেতরে human-approval নেওয়া
        হয় — approve না হলে কিছুই ইনস্টল হবে না।

        Args:
            package_name: যেই প্যাকেজ ইনস্টল করতে হবে তার সঠিক নাম
        """
        manager = detect_package_manager()
        if not manager:
            return json.dumps({"status": "error", "error": "সাপোর্টেড প্যাকেজ ম্যানেজার পাওয়া যায়নি।"})
        if not await _require_approval(f"প্যাকেজ ইনস্টল: {package_name}",
                                        f"'{manager}' দিয়ে সিস্টেমে '{package_name}' ইনস্টল করা হবে।"):
            return json.dumps({"status": "denied", "package": package_name})
        snap = await _snapshot_before(f"প্যাকেজ ইনস্টলের আগে: {package_name}")
        result = _run(PACKAGE_MANAGERS[manager]["install"](package_name), needs_root=True, timeout=600)
        result["snapshot"] = snap
        return json.dumps(result, ensure_ascii=False)

    async def remove_package(self, package_name: str) -> str:
        """একটা প্যাকেজ আনইনস্টল/রিমুভ করো (approval লাগবে)।

        Args:
            package_name: যেই প্যাকেজ রিমুভ করতে হবে তার সঠিক নাম
        """
        manager = detect_package_manager()
        if not manager:
            return json.dumps({"status": "error", "error": "সাপোর্টেড প্যাকেজ ম্যানেজার পাওয়া যায়নি।"})
        if not await _require_approval(f"প্যাকেজ রিমুভ: {package_name}",
                                        f"'{manager}' দিয়ে সিস্টেম থেকে '{package_name}' রিমুভ করা হবে।"):
            return json.dumps({"status": "denied", "package": package_name})
        snap = await _snapshot_before(f"প্যাকেজ রিমুভের আগে: {package_name}")
        result = _run(PACKAGE_MANAGERS[manager]["remove"](package_name), needs_root=True, timeout=300)
        result["snapshot"] = snap
        return json.dumps(result, ensure_ascii=False)

    async def update_system(self, upgrade: bool = False) -> str:
        """প্যাকেজ ইনডেক্স রিফ্রেশ করো; upgrade=True দিলে ইনস্টল করা সব প্যাকেজও
        আপগ্রেড করবে (approval লাগবে)।

        Args:
            upgrade: True হলে update-এর পর পুরো সিস্টেম upgrade-ও করবে
        """
        manager = detect_package_manager()
        if not manager:
            return json.dumps({"status": "error", "error": "সাপোর্টেড প্যাকেজ ম্যানেজার পাওয়া যায়নি।"})
        action = "সিস্টেম আপগ্রেড (update + upgrade)" if upgrade else "প্যাকেজ ইনডেক্স আপডেট"
        if not await _require_approval(action, f"'{manager}' দিয়ে {action} করা হবে।"):
            return json.dumps({"status": "denied"})
        snap = await _snapshot_before(action) if upgrade else {"status": "skipped", "message": "শুধু ইনডেক্স আপডেট, upgrade না — স্ন্যাপশট দরকার নেই।"}
        results = [_run(PACKAGE_MANAGERS[manager]["update"](), needs_root=True, timeout=300)]
        if upgrade:
            results.append(_run(PACKAGE_MANAGERS[manager]["upgrade"](), needs_root=True, timeout=1800))
        return json.dumps({"status": "ok", "steps": results, "snapshot": snap}, ensure_ascii=False)


class SystemServiceTools(Toolkit):
    """systemd সার্ভিস কন্ট্রোল। status/list শুধু পড়ে (approval লাগে না)।
    start/stop/restart/enable/disable-এ approval লাগবে, আর
    PROTECTED_UNIT_PATTERNS-এ থাকা ইউনিট কখনোই টাচ করা যাবে না।"""

    def __init__(self, **kwargs):
        super().__init__(
            name="system_service_tools",
            tools=[self.service_status, self.list_services, self.control_service],
            **kwargs,
        )

    def _is_protected(self, unit: str) -> bool:
        return any(re.match(pat, unit) for pat in PROTECTED_UNIT_PATTERNS)

    def service_status(self, unit_name: str) -> str:
        """একটা systemd সার্ভিসের স্ট্যাটাস দেখো (approval লাগে না)।

        Args:
            unit_name: যেমন "nginx" বা "docker.service"
        """
        return json.dumps(_run(["systemctl", "status", unit_name, "--no-pager"], needs_root=False, timeout=15),
                           ensure_ascii=False)

    def list_services(self, pattern: str = "") -> str:
        """চলমান/ইনস্টল করা সার্ভিসের লিস্ট দেখো।

        Args:
            pattern: ঐচ্ছিক ফিল্টার (যেমন "nginx" দিলে nginx-সংশ্লিষ্ট ইউনিট)
        """
        argv = ["systemctl", "list-units", "--type=service", "--all", "--no-pager"]
        if pattern:
            argv.append(f"{pattern}*")
        return json.dumps(_run(argv, needs_root=False, timeout=15), ensure_ascii=False)

    async def control_service(self, unit_name: str, action: str) -> str:
        """একটা systemd সার্ভিস start/stop/restart/enable/disable করো (approval লাগবে)।

        Args:
            unit_name: যেমন "nginx"
            action: "start" | "stop" | "restart" | "enable" | "disable"
        """
        if action not in ("start", "stop", "restart", "enable", "disable"):
            return json.dumps({"status": "error",
                                "error": "action অবশ্যই start/stop/restart/enable/disable-এর একটা হতে হবে।"})
        if self._is_protected(unit_name):
            return json.dumps({
                "status": "blocked",
                "error": f"'{unit_name}' সুরক্ষিত ইউনিট (network/ssh/dbus/systemd-core/এই সিস্টেম নিজেই) — "
                         f"কোডে হার্ড-ব্লক করা, approval দিলেও {action} করা যাবে না।",
            }, ensure_ascii=False)
        if not await _require_approval(f"সার্ভিস {action}: {unit_name}",
                                        f"systemd সার্ভিস '{unit_name}'-এ '{action}' চালানো হবে।"):
            return json.dumps({"status": "denied"})
        snap = await _snapshot_before(f"সার্ভিস {action} ({unit_name})-এর আগে")
        result = _run(["systemctl", action, unit_name], needs_root=True, timeout=60)
        result["snapshot"] = snap
        return json.dumps(result, ensure_ascii=False)
