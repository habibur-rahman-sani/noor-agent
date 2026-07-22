"""
desktop_control.py
===================
"মানুষ কম্পিউটার দিয়ে যা যা করতে পারে" তার মূল অংশ — মাউস/কীবোর্ড/উইন্ডো/ক্লিপবোর্ড
নিয়ন্ত্রণ এবং অ্যাপ্লিকেশন চালু করা। PC Agent এই toolkit ব্যবহার করে।

ডিজাইন সিদ্ধান্ত:
- Linux-এ **X11**-এর জন্য `xdotool`/`wmctrl` প্রাধান্য পায় (হালকা, নির্ভরযোগ্য,
  root লাগে না)। এগুলো না থাকলে `pyautogui` fallback হিসেবে ব্যবহৃত হয়।
- **Wayland**-এ xdotool/pyautogui সীমিত/কাজ নাও করতে পারে (Wayland-এর সিকিউরিটি
  মডেল ইচ্ছাকৃতভাবে গ্লোবাল ইনপুট-ইনজেকশন আটকায়) — এই সীমাবদ্ধতা কোডে ডিটেক্ট
  করে স্পষ্টভাবে জানানো হয়, চুপচাপ ব্যর্থ হয় না।
- অ্যাপ্লিকেশন চালু করা ও উইন্ডো বন্ধ করা — এই দুটো "state বদলে দেওয়া" অ্যাকশনে
  approval-gate লাগে (guardrail.py)। মাউস/কীবোর্ড/স্ক্রল-এর মতো মুহূর্তের মধ্যে
  ঘটা মাইক্রো-অ্যাকশনে approval লাগানো হয়নি (প্রতি ক্লিকে approval চাইলে ব্যবহারযোগ্য
  থাকবে না) — তার বদলে PC Agent-এর instructions-এ স্পষ্ট সতর্কতা আছে
  (পাসওয়ার্ড/স্পর্শকাতর ফিল্ডে টাইপ করার আগে নিশ্চিত হওয়া)।
"""
import json
import logging
import os
import shutil
import subprocess

from agno.tools.toolkit import Toolkit

logger = logging.getLogger("desktop_control")


def _is_wayland() -> bool:
    return os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"


def _has_display() -> bool:
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _run(argv: list, timeout: int = 15) -> dict:
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return {"status": "ok" if result.returncode == 0 else "failed",
                "returncode": result.returncode, "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip()}
    except FileNotFoundError:
        return {"status": "error", "error": f"'{argv[0]}' পাওয়া যায়নি — ইনস্টল করা আছে কিনা যাচাই করো।"}
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": "সময়সীমা পার হয়ে গেছে (timeout)।"}
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "error": str(e)}


async def _require_approval(action: str, details: str) -> bool:
    """async — ব্লকিং অপেক্ষাটা আলাদা থ্রেডে হয় (guardrail.wait_for_approval_async),
    তাই এই কল চলাকালীন সার্ভারের বাকি সেশন আটকায় না।"""
    try:
        from guardrail import create_pending_approval, wait_for_approval_async
    except Exception:
        logger.error("guardrail মডিউল লোড করা যায়নি — নিরাপত্তার জন্য অ্যাকশন deny করা হলো।")
        return False
    request_id = create_pending_approval(action, details)
    return await wait_for_approval_async(request_id)


def _display_check() -> str | None:
    """ডিসপ্লে/GUI না থাকলে বা Wayland হলে স্পষ্ট মেসেজ রিটার্ন করে, নাহলে None।"""
    if not _has_display():
        return "কোনো GUI ডিসপ্লে পাওয়া যায়নি (হেডলেস সার্ভার/SSH সেশন) — ডেস্কটপ কন্ট্রোল এখানে কাজ করবে না।"
    if _is_wayland() and not shutil.which("ydotool"):
        return (
            "এটা Wayland সেশন — xdotool/pyautogui সাধারণত Wayland-এ কাজ করে না (নিরাপত্তার কারণে "
            "Wayland গ্লোবাল ইনপুট-ইনজেকশন আটকায়)। বিকল্প: 'ydotool' ইনস্টল করো (Wayland-compatible), "
            "অথবা X11 সেশনে লগইন করো।"
        )
    return None


class DesktopControlTools(Toolkit):
    """মাউস, কীবোর্ড, উইন্ডো, ক্লিপবোর্ড ও অ্যাপ্লিকেশন — ডেস্কটপের প্রায় সবকিছু নিয়ন্ত্রণের টুল।"""

    def __init__(self, **kwargs):
        super().__init__(
            name="desktop_control_tools",
            tools=[
                self.move_and_click, self.type_text, self.press_key,
                self.list_windows, self.focus_window, self.close_window,
                self.get_clipboard, self.set_clipboard, self.launch_application,
                self.click_text, self.click_icon,
            ],
            **kwargs,
        )

    # ------------------------------------------------------------ input ---

    def move_and_click(self, x: int, y: int, button: str = "left", double: bool = False) -> str:
        """মাউস একটা স্ক্রিন-কোঅর্ডিনেটে নিয়ে ক্লিক করো (কোঅর্ডিনেট জানার জন্য আগে
        Vision Agent-এর read_screen_text বা স্ক্রিনশট ব্যবহার করে দেখে নাও কোথায় কী আছে)।

        Args:
            x: স্ক্রিনের x কোঅর্ডিনেট (পিক্সেল)
            y: স্ক্রিনের y কোঅর্ডিনেট (পিক্সেল)
            button: "left" | "right" | "middle"
            double: True হলে ডাবল-ক্লিক
        """
        err = _display_check()
        if err:
            return err
        if shutil.which("xdotool"):
            argv = ["xdotool", "mousemove", str(x), str(y), "click"]
            if double:
                argv += ["--repeat", "2", "--delay", "150"]
            argv.append({"left": "1", "middle": "2", "right": "3"}.get(button, "1"))
            return json.dumps(_run(argv), ensure_ascii=False)
        try:
            import pyautogui
            pyautogui.moveTo(x, y)
            (pyautogui.doubleClick if double else pyautogui.click)(button=button)
            return json.dumps({"status": "ok"}, ensure_ascii=False)
        except Exception as e:  # noqa: BLE001
            return f"মাউস কন্ট্রোল ব্যর্থ ({e}) — 'sudo apt install xdotool' অথবা 'pip install pyautogui' করো।"

    def type_text(self, text: str) -> str:
        """বর্তমানে ফোকাসড ফিল্ডে টেক্সট টাইপ করো।

        Args:
            text: যা টাইপ করতে হবে
        """
        err = _display_check()
        if err:
            return err
        if shutil.which("xdotool"):
            return json.dumps(_run(["xdotool", "type", "--clearmodifiers", text]), ensure_ascii=False)
        try:
            import pyautogui
            pyautogui.typewrite(text)
            return json.dumps({"status": "ok"}, ensure_ascii=False)
        except Exception as e:  # noqa: BLE001
            return f"টাইপিং ব্যর্থ ({e}) — 'sudo apt install xdotool' অথবা 'pip install pyautogui' করো।"

    def press_key(self, key: str) -> str:
        """একটা কী/কী-কম্বিনেশন প্রেস করো (যেমন "Return", "ctrl+c", "alt+Tab", "Escape")।

        Args:
            key: xdotool-স্টাইল কী-নাম, '+' দিয়ে কম্বিনেশন
        """
        err = _display_check()
        if err:
            return err
        if shutil.which("xdotool"):
            return json.dumps(_run(["xdotool", "key", key.replace("+", "+")]), ensure_ascii=False)
        try:
            import pyautogui
            keys = key.split("+")
            if len(keys) > 1:
                pyautogui.hotkey(*keys)
            else:
                pyautogui.press(key)
            return json.dumps({"status": "ok"}, ensure_ascii=False)
        except Exception as e:  # noqa: BLE001
            return f"কী-প্রেস ব্যর্থ ({e}) — 'sudo apt install xdotool' অথবা 'pip install pyautogui' করো।"

    # ---------------------------------------------------------- windows ---

    def list_windows(self) -> str:
        """খোলা সব উইন্ডোর তালিকা (id + শিরোনাম) দেখাও।"""
        err = _display_check()
        if err:
            return err
        if not shutil.which("wmctrl"):
            return "'wmctrl' পাওয়া যায়নি — 'sudo apt install wmctrl' করো।"
        return json.dumps(_run(["wmctrl", "-l"]), ensure_ascii=False)

    def focus_window(self, title_substring: str) -> str:
        """শিরোনামে দেওয়া টেক্সট আছে এমন উইন্ডো সামনে আনো (ফোকাস করো)।

        Args:
            title_substring: উইন্ডোর শিরোনামের অংশবিশেষ (case-insensitive)
        """
        err = _display_check()
        if err:
            return err
        if not shutil.which("wmctrl"):
            return "'wmctrl' পাওয়া যায়নি — 'sudo apt install wmctrl' করো।"
        return json.dumps(_run(["wmctrl", "-a", title_substring]), ensure_ascii=False)

    async def close_window(self, title_substring: str) -> str:
        """শিরোনামে দেওয়া টেক্সট আছে এমন উইন্ডো বন্ধ করো (approval লাগবে — সেভ না করা
        কাজ থাকলে হারিয়ে যেতে পারে)।

        Args:
            title_substring: উইন্ডোর শিরোনামের অংশবিশেষ
        """
        err = _display_check()
        if err:
            return err
        if not shutil.which("wmctrl"):
            return "'wmctrl' পাওয়া যায়নি — 'sudo apt install wmctrl' করো।"
        if not await _require_approval("উইন্ডো বন্ধ করা", f"শিরোনামে '{title_substring}' আছে এমন উইন্ডো বন্ধ করা হবে — সেভ না করা কাজ হারাতে পারে।"):
            return json.dumps({"status": "denied"}, ensure_ascii=False)
        return json.dumps(_run(["wmctrl", "-c", title_substring]), ensure_ascii=False)

    # -------------------------------------------------------- clipboard ---

    def get_clipboard(self) -> str:
        """ক্লিপবোর্ডের বর্তমান কনটেন্ট পড়ো।"""
        for tool, argv in (("xclip", ["xclip", "-selection", "clipboard", "-o"]),
                            ("xsel", ["xsel", "--clipboard", "--output"])):
            if shutil.which(tool):
                r = _run(argv)
                return r.get("stdout", "") if r.get("status") == "ok" else json.dumps(r, ensure_ascii=False)
        return "ক্লিপবোর্ড টুল পাওয়া যায়নি — 'sudo apt install xclip' করো।"

    def set_clipboard(self, text: str) -> str:
        """ক্লিপবোর্ডে টেক্সট সেট করো।

        Args:
            text: ক্লিপবোর্ডে যা বসাতে হবে
        """
        for tool, argv in (("xclip", ["xclip", "-selection", "clipboard"]),
                            ("xsel", ["xsel", "--clipboard", "--input"])):
            if shutil.which(tool):
                try:
                    subprocess.run(argv, input=text, text=True, timeout=10, check=True)
                    return "ক্লিপবোর্ডে সেট হয়েছে।"
                except Exception as e:  # noqa: BLE001
                    return f"ব্যর্থ: {e}"
        return "ক্লিপবোর্ড টুল পাওয়া যায়নি — 'sudo apt install xclip' করো।"

    # -------------------------------------------------- vision + click ---

    def click_text(self, query: str, region: str | None = None, match_index: int = 0) -> str:
        """স্ক্রিনে একটা টেক্সট/বাটন-লেবেল খুঁজে সরাসরি সেখানে ক্লিক করো — 'দেখা' আর
        'ক্লিক করা' দুটো ধাপ একসাথে (ভেতরে ScreenTools.locate_text + move_and_click
        ব্যবহার করে)। একাধিক ম্যাচ পেলে ডিফল্ট সবচেয়ে confident (সবচেয়ে নিশ্চিত)
        ম্যাচে ক্লিক করে — নির্দিষ্ট একটা বেছে নিতে match_index দাও।

        Args:
            query: যেই টেক্সট/বাটনে ক্লিক করতে হবে, যেমন "Save" বা "Sign In"
            region: ঐচ্ছিক — "left,top,width,height", না দিলে পুরো স্ক্রিন
            match_index: একাধিক ম্যাচ থাকলে কোনটায় ক্লিক করতে হবে (0 = সবচেয়ে confident)
        """
        err = _display_check()
        if err:
            return err
        try:
            from agents.vision_agent import ScreenTools
        except Exception as e:  # noqa: BLE001
            return f"Vision টুল লোড করা যায়নি ({e}) — locate_text আলাদাভাবে চালানোর চেষ্টা করো।"

        result_raw = ScreenTools().locate_text(query, region=region)
        try:
            result = json.loads(result_raw)
        except Exception:
            return f"locate_text-এর ফলাফল বোঝা যায়নি: {result_raw}"

        if result.get("status") != "found":
            return result_raw  # not_found/error — যেমন আছে তেমন ফেরত দাও, স্পষ্ট মেসেজসহ

        matches = result["matches"]
        if match_index >= len(matches):
            return json.dumps({
                "status": "error",
                "error": f"match_index={match_index} কিন্তু মাত্র {len(matches)}টা ম্যাচ পাওয়া গেছে।",
            }, ensure_ascii=False)

        m = matches[match_index]
        click_result = self.move_and_click(m["x"], m["y"])
        return json.dumps({
            "status": "clicked", "matched_text": m["matched_text"],
            "x": m["x"], "y": m["y"], "click_result": json.loads(click_result) if click_result.strip().startswith("{") else click_result,
            "other_matches": len(matches) - 1,
        }, ensure_ascii=False)

    def click_icon(self, description: str, region: str | None = None) -> str:
        """click_text (OCR) কাজ না করলে — বিশেষত টেক্সট-বিহীন আইকন-শুধু বাটনে — এটা ব্যবহার করো।
        ভেতরে ScreenTools.locate_icon (vision-LLM ভিত্তিক) + move_and_click ব্যবহার করে, তাই
        'দেখা' আর 'ক্লিক করা' একসাথে হয়। click_text-এর চেয়ে ধীর/ব্যয়সাপেক্ষ — টেক্সট-লেবেলযুক্ত
        উপাদানে আগে click_text ব্যবহার করো, এটা মূলত fallback।

        Args:
            description: যা খুঁজতে হবে স্পষ্টভাবে বর্ণনা করো, যেমন "উপরে-ডানদিকে সেটিংস গিয়ার আইকন"
            region: ঐচ্ছিক — "left,top,width,height", না দিলে পুরো স্ক্রিন
        """
        err = _display_check()
        if err:
            return err
        try:
            from agents.vision_agent import ScreenTools
        except Exception as e:  # noqa: BLE001
            return f"Vision টুল লোড করা যায়নি ({e}) — locate_icon আলাদাভাবে চালানোর চেষ্টা করো।"

        result_raw = ScreenTools().locate_icon(description, region=region)
        try:
            result = json.loads(result_raw)
        except Exception:
            return f"locate_icon-এর ফলাফল বোঝা যায়নি: {result_raw}"

        if result.get("status") != "found":
            return result_raw  # not_found/error — যেমন আছে তেমন ফেরত দাও, স্পষ্ট মেসেজসহ

        m = result["matches"][0]
        click_result = self.move_and_click(m["x"], m["y"])
        return json.dumps({
            "status": "clicked", "matched_description": m["matched_text"],
            "x": m["x"], "y": m["y"],
            "confidence": m.get("confidence"), "reason": m.get("reason", ""),
            "click_result": json.loads(click_result) if click_result.strip().startswith("{") else click_result,
        }, ensure_ascii=False)

    # ------------------------------------------------------- app launch ---

    async def launch_application(self, command: str) -> str:
        """একটা অ্যাপ্লিকেশন চালু করো (approval লাগবে — এটা কার্যত arbitrary কমান্ড চালানো)।

        Args:
            command: চালানোর কমান্ড, যেমন "firefox", "gnome-calculator", "code ."
        """
        err = _display_check()
        if err:
            return err
        if not await _require_approval("অ্যাপ্লিকেশন চালু করা", f"কমান্ড চালানো হবে: '{command}'"):
            return json.dumps({"status": "denied"}, ensure_ascii=False)
        try:
            subprocess.Popen(command.split(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            return f"'{command}' চালু করা হয়েছে।"
        except Exception as e:  # noqa: BLE001
            return f"চালু করা যায়নি: {e}"
