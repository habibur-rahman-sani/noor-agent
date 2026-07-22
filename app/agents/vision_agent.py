"""
vision_agent.py
================
Vision এজেন্ট — স্ক্রিন দেখতে পারা (perception layer)। AI OS-এর "চোখ"।

Agno-তে রেডিমেড "screen reading" টুলকিট নেই, তাই এখানে একটা কাস্টম ScreenTools
toolkit বানানো হয়েছে: স্ক্রিনশট নেওয়া (mss/PIL) + OCR (pytesseract)।

গুরুত্বপূর্ণ ডিজাইন নোট (আগের ভার্সনের একটা ফাঁক ফিক্স করা হয়েছে):
আগে `read_screen_text` শুধু প্লেইন টেক্সট রিটার্ন করত — কোনো কোঅর্ডিনেট ছাড়া।
ফলে PC Agent স্ক্রিনে কী লেখা আছে "পড়তে" পারলেও কোথায় ক্লিক করতে হবে সেটা জানতে
পারত না (move_and_click-এর জন্য x,y লাগে)। এখন `locate_text` আছে, যেটা
`pytesseract.image_to_data` (বাউন্ডিং-বক্স-সহ OCR) ব্যবহার করে প্রতিটা শব্দ/লাইনের
স্ক্রিন-কোঅর্ডিনেট রিটার্ন করে — তাই "Save বাটনে ক্লিক করো" জাতীয় কাজ এখন আসলেই
সম্ভব (দেখো -> লোকেট করো -> ক্লিক করো)।

আপডেট: locate_text (OCR) টেক্সট-বিহীন আইকন/গ্রাফিক্যাল বাটনে কাজ করে না (সেক্ষেত্রে
"not_found" রিটার্ন করে, চুপচাপ ভুল কোঅর্ডিনেট দেয় না) — এই বাকি ফাঁকটা এখন `locate_icon`
দিয়ে ঢাকা হয়েছে, যা স্ক্রিনশট সরাসরি একটা মাল্টিমোডাল vision-LLM-কে পাঠিয়ে ("এই বাটনটা
কোথায়") কোঅর্ডিনেট বের করে — এটাই আসল "computer-use" প্যাটার্ন। locate_text দ্রুত ও সস্তা
বলে টেক্সট-লেবেলযুক্ত উপাদানে সেটাই প্রথমে চেষ্টা করা উচিত, locate_icon মূলত ধীর/ব্যয়সাপেক্ষ
fallback (বিশেষত ক্লাউড/OpenRouter মোডে)।

ইনস্টলেশন প্রয়োজন (requirements.txt-এ যোগ করা আছে):
    pip install mss pillow pytesseract
    Tesseract OCR engine সিস্টেমে আলাদাভাবে ইনস্টল থাকা লাগবে:
        sudo apt install tesseract-ocr tesseract-ocr-ben
    key/টুল না থাকলে agent সেটা বলে দেবে, সিস্টেম ক্র্যাশ করবে না।
"""
import json
import os
import tempfile

from agno.agent import Agent
from agno.tools.toolkit import Toolkit
from config import get_model, get_db, MEMORY_KWARGS, ask_vision_model


class ScreenTools(Toolkit):
    """স্ক্রিনশট নেওয়া, স্ক্রিনে টেক্সট পড়া, এবং নির্দিষ্ট টেক্সট কোথায় আছে
    (ক্লিক করার জন্য দরকারি x,y কোঅর্ডিনেট) খুঁজে বের করার টুল।"""

    def __init__(self, **kwargs):
        super().__init__(
            name="screen_tools",
            tools=[self.take_screenshot, self.read_screen_text, self.locate_text, self.locate_icon],
            **kwargs,
        )

    def take_screenshot(self, save_path: str = "screenshot.png") -> str:
        """পুরো স্ক্রিনের একটা স্ক্রিনশট নিয়ে ফাইলে সেভ করে।

        Args:
            save_path: স্ক্রিনশট যেখানে সেভ হবে
        """
        try:
            import mss
            with mss.mss() as sct:
                monitor = sct.monitors[0]
                img = sct.grab(monitor)
                mss.tools.to_png(img.rgb, img.size, output=save_path)
            return f"স্ক্রিনশট সেভ হয়েছে: {save_path}"
        except Exception as e:  # noqa: BLE001
            return f"স্ক্রিনশট নেওয়া যায়নি ({e}) — 'pip install mss' করা আছে কিনা, এবং হেডলেস/SSH সেশনে ডিসপ্লে অ্যাক্সেস আছে কিনা যাচাই করো।"

    def _grab(self, region: str | None):
        import mss
        with mss.mss() as sct:
            if region:
                l, t, w, h = (int(x) for x in region.split(","))
                monitor = {"left": l, "top": t, "width": w, "height": h}
            else:
                monitor = sct.monitors[0]
            shot = sct.grab(monitor)
            return shot, monitor

    def read_screen_text(self, region: str | None = None) -> str:
        """স্ক্রিনশট নিয়ে তার উপর OCR করে টেক্সট বের করে (কোন উইন্ডোতে কী লেখা আছে
        বোঝার জন্য — শুধু পড়ার জন্য, ক্লিক করার কোঅর্ডিনেট লাগলে locate_text ব্যবহার করো)।

        Args:
            region: ঐচ্ছিক — "left,top,width,height" ফরম্যাটে নির্দিষ্ট অংশ, না দিলে পুরো স্ক্রিন
        """
        try:
            import pytesseract
            from PIL import Image

            shot, _ = self._grab(region)
            img = Image.frombytes("RGB", shot.size, shot.rgb)
            text = pytesseract.image_to_string(img, lang="ben+eng")
            return text.strip() or "(স্ক্রিনে কোনো টেক্সট পাওয়া যায়নি)"
        except Exception as e:  # noqa: BLE001
            return (
                f"স্ক্রিন OCR ব্যর্থ হয়েছে ({e}) — যাচাই করো: "
                "'pip install mss pytesseract pillow' এবং সিস্টেমে Tesseract OCR ইনস্টল আছে কিনা।"
            )

    def locate_text(self, query: str, region: str | None = None) -> str:
        """স্ক্রিনে দেওয়া টেক্সট (বা তার কাছাকাছি) কোথায় আছে খুঁজে বের করে — ফলাফলে
        প্রতিটা ম্যাচের কেন্দ্রের x,y কোঅর্ডিনেট থাকে, যা সরাসরি
        DesktopControlTools.move_and_click(x, y)-এ ব্যবহার করা যায়। একাধিক শব্দ
        মিলিয়ে একসাথে থাকা লাইন/লেবেলও (যেমন বাটনের টেক্সট) ম্যাচ করার চেষ্টা করে।
        একাধিক ম্যাচ পাওয়া গেলে সবচেয়ে confident (সবচেয়ে বেশি OCR-নিশ্চয়তা) ওয়ালাটা
        প্রথমে দেখানো হয়, কিন্তু ভুল জায়গায় ক্লিক এড়াতে সব ম্যাচ দেখেই সিদ্ধান্ত নেওয়া ভালো।

        Args:
            query: যেই টেক্সট খুঁজতে হবে (case-insensitive, আংশিক মিলও ধরা হয়), যেমন "Save" বা "Submit"
            region: ঐচ্ছিক — "left,top,width,height", না দিলে পুরো স্ক্রিন
        """
        try:
            import pytesseract
            from PIL import Image

            shot, monitor = self._grab(region)
            img = Image.frombytes("RGB", shot.size, shot.rgb)
            offset_x, offset_y = monitor.get("left", 0), monitor.get("top", 0)

            data = pytesseract.image_to_data(
                img, lang="ben+eng", output_type=pytesseract.Output.DICT
            )

            n = len(data["text"])
            words = [
                {
                    "text": data["text"][i].strip(),
                    "conf": float(data["conf"][i]) if str(data["conf"][i]).lstrip("-").isdigit() else -1.0,
                    "left": data["left"][i], "top": data["top"][i],
                    "width": data["width"][i], "height": data["height"][i],
                    "line_num": data["line_num"][i], "block_num": data["block_num"][i],
                }
                for i in range(n) if data["text"][i].strip()
            ]

            q = query.strip().lower()
            matches = []

            # ধাপ ১: একক শব্দ ম্যাচ
            for w in words:
                if q in w["text"].lower():
                    cx = offset_x + w["left"] + w["width"] // 2
                    cy = offset_y + w["top"] + w["height"] // 2
                    matches.append({"matched_text": w["text"], "x": cx, "y": cy,
                                     "confidence": w["conf"], "match_type": "word"})

            # ধাপ ২: একই লাইনের একাধিক শব্দ জোড়া লাগিয়ে বাক্যাংশ ম্যাচ (যেমন "Sign In")
            if " " in q:
                from collections import defaultdict
                by_line = defaultdict(list)
                for w in words:
                    by_line[(w["block_num"], w["line_num"])].append(w)
                for line_words in by_line.values():
                    line_text = " ".join(w["text"] for w in line_words).lower()
                    if q in line_text:
                        l = min(w["left"] for w in line_words)
                        t = min(w["top"] for w in line_words)
                        r = max(w["left"] + w["width"] for w in line_words)
                        b = max(w["top"] + w["height"] for w in line_words)
                        avg_conf = sum(w["conf"] for w in line_words) / len(line_words)
                        matches.append({
                            "matched_text": " ".join(w["text"] for w in line_words),
                            "x": offset_x + (l + r) // 2, "y": offset_y + (t + b) // 2,
                            "confidence": avg_conf, "match_type": "phrase",
                        })

            if not matches:
                return json.dumps({
                    "status": "not_found",
                    "message": f"'{query}' স্ক্রিনে খুঁজে পাওয়া যায়নি — নিশ্চিত হও এটা এখন দৃশ্যমান কিনা "
                               f"(অন্য উইন্ডোর আড়ালে নয় তো), অথবা এটা টেক্সট না হয়ে আইকন/ছবি হতে পারে "
                               f"যা OCR ধরতে পারে না।",
                }, ensure_ascii=False)

            matches.sort(key=lambda m: m["confidence"], reverse=True)
            return json.dumps({"status": "found", "matches": matches[:5]}, ensure_ascii=False)
        except Exception as e:  # noqa: BLE001
            return json.dumps({
                "status": "error",
                "error": f"'pip install mss pytesseract pillow' এবং Tesseract OCR ইনস্টল আছে কিনা যাচাই করো: {e}",
            }, ensure_ascii=False)

    def locate_icon(self, description: str, region: str | None = None) -> str:
        """locate_text (OCR) কাজ না করলে — যেমন টেক্সট-বিহীন আইকন-শুধু বাটনে (গিয়ার/হ্যামবার্গার/
        ক্রস আইকন ইত্যাদি) — এই টুল ব্যবহার করো। স্ক্রিনশট একটা মাল্টিমোডাল vision-LLM-কে
        পাঠিয়ে বর্ণনা দেওয়া উপাদানটার x,y কোঅর্ডিনেট জিজ্ঞেস করে (আসল "computer-use" প্যাটার্ন) —
        ফলাফল সরাসরি move_and_click(x, y)-এ ব্যবহারযোগ্য।

        locate_text-এর চেয়ে ধীর ও (ক্লাউড/OpenRouter মোডে) কিছুটা ব্যয়সাপেক্ষ, তাই টেক্সট-লেবেলযুক্ত
        বাটনে আগে locate_text/click_text ব্যবহার করাই ভালো — এটা মূলত fallback।

        Args:
            description: যা খুঁজতে হবে স্পষ্টভাবে বর্ণনা করো — অবস্থানসহ যত নির্দিষ্ট তত ভালো ফল,
                যেমন "উপরে-ডানদিকের কোণায় গিয়ার/সেটিংস আইকন" বা "লাল রঙের বন্ধ করার (X) বাটন"
            region: ঐচ্ছিক — "left,top,width,height", না দিলে পুরো স্ক্রিন
        """
        try:
            from PIL import Image
        except Exception as e:  # noqa: BLE001
            return json.dumps({
                "status": "error",
                "error": f"Pillow ইনস্টল নেই ({e}) — 'pip install pillow' করো।",
            }, ensure_ascii=False)

        try:
            shot, monitor = self._grab(region)
        except Exception as e:  # noqa: BLE001
            return json.dumps({
                "status": "error",
                "error": f"স্ক্রিনশট নেওয়া যায়নি ({e}) — ডিসপ্লে অ্যাক্সেস আছে কিনা যাচাই করো।",
            }, ensure_ascii=False)

        offset_x, offset_y = monitor.get("left", 0), monitor.get("top", 0)
        img = Image.frombytes("RGB", shot.size, shot.rgb)
        orig_w, orig_h = img.size

        # বড় রেজোলিউশন vision মডেলে পাঠানো ধীর ও (ক্লাউড মোডে) ব্যয়সাপেক্ষ — তাই সীমিত করা,
        # কিন্তু scale মনে রেখে পরে আসল স্ক্রিন-কোঅর্ডিনেটে ফিরিয়ে আনা হয়
        max_dim = 1024
        scale = min(1.0, max_dim / max(orig_w, orig_h))
        resized = img.resize((max(1, round(orig_w * scale)), max(1, round(orig_h * scale)))) if scale < 1.0 else img
        rw, rh = resized.size

        tmp_path = os.path.join(tempfile.gettempdir(), "agno_vision_locate_icon.png")
        try:
            resized.save(tmp_path)
        except Exception as e:  # noqa: BLE001
            return json.dumps({"status": "error", "error": f"ছবি সেভ করা যায়নি: {e}"}, ensure_ascii=False)

        prompt = (
            f"তুমি একটা কম্পিউটার স্ক্রিনশট দেখছো (রেজোলিউশন {rw}x{rh} পিক্সেল, উপরে-বামে (0,0) থেকে শুরু)। "
            f"এতে খুঁজে বের করো: '{description}'। "
            "শুধুই নিচের JSON ফরম্যাটে উত্তর দাও — কোনো ব্যাখ্যা, মার্কডাউন কোড-ফেন্স, বা অতিরিক্ত টেক্সট ছাড়া:\n"
            '{"found": true, "x": <int>, "y": <int>, "confidence": <0.0-1.0>, "reason": "<সংক্ষিপ্ত কারণ>"}\n'
            'অথবা যদি খুঁজে না পাও:\n'
            '{"found": false, "reason": "<কেন পাওনি>"}\n'
            "x,y অবশ্যই এই ছবিরই পিক্সেল কোঅর্ডিনেটে হতে হবে (উপাদানটার কেন্দ্রবিন্দু), অন্য কোনো স্কেলে না।"
        )

        result = ask_vision_model(tmp_path, prompt)
        if result["status"] != "ok":
            return json.dumps({"status": "error", "error": result["error"]}, ensure_ascii=False)

        raw_text = result["text"].strip()
        if "```" in raw_text:
            for part in raw_text.split("```"):
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    raw_text = part
                    break

        start, end = raw_text.find("{"), raw_text.rfind("}")
        if start == -1 or end == -1:
            return json.dumps({
                "status": "error",
                "error": f"vision মডেলের উত্তর JSON হিসেবে বোঝা যায়নি: {raw_text[:300]}",
            }, ensure_ascii=False)

        try:
            parsed = json.loads(raw_text[start:end + 1])
        except Exception as e:  # noqa: BLE001
            return json.dumps({
                "status": "error",
                "error": f"vision মডেলের উত্তর JSON পার্স করা যায়নি ({e}): {raw_text[:300]}",
            }, ensure_ascii=False)

        if not parsed.get("found"):
            return json.dumps({
                "status": "not_found",
                "message": parsed.get("reason", f"'{description}' vision মডেল খুঁজে পায়নি।"),
            }, ensure_ascii=False)

        try:
            rx, ry = float(parsed["x"]), float(parsed["y"])
        except (KeyError, TypeError, ValueError):
            return json.dumps({
                "status": "error",
                "error": f"vision মডেল found:true দিয়েছে কিন্তু বৈধ x,y দেয়নি: {parsed}",
            }, ensure_ascii=False)

        real_x = offset_x + round(rx / scale)
        real_y = offset_y + round(ry / scale)

        return json.dumps({
            "status": "found",
            "matches": [{
                "matched_text": description,
                "x": real_x, "y": real_y,
                "confidence": parsed.get("confidence", 0.5),
                "match_type": "vision",
                "reason": parsed.get("reason", ""),
            }],
        }, ensure_ascii=False)


vision_agent = Agent(
    name="Vision Agent",
    role="স্ক্রিনশট নেওয়া, স্ক্রিনে কী আছে (টেক্সট/UI) তা পড়া, এবং নির্দিষ্ট টেক্সট/বাটনের ক্লিক-করার-উপযোগী কোঅর্ডিনেট বের করা — সিস্টেমের 'চোখ' হিসেবে কাজ করা",
    model=get_model("general"),
    db=get_db(),
    tools=[ScreenTools()],
    instructions=[
        "ইউজার স্ক্রিনে কী আছে জানতে চাইলে read_screen_text ব্যবহার করো।",
        "কোনো বাটন/লিংক/লেবেলে ক্লিক করার জন্য কোঅর্ডিনেট দরকার হলে locate_text ব্যবহার করো — "
        "এটাই PC Agent-কে move_and_click-এর জন্য x,y দেয়।",
        "locate_text একাধিক ম্যাচ দিলে সবগুলো দেখাও এবং কোনটা সঠিক মনে হচ্ছে বলে দাও (নিশ্চিত না হলে "
        "জিজ্ঞেস করো), যাতে ভুল জায়গায় ক্লিক না হয়।",
        "locate_text 'not_found' দিলে (বিশেষত আইকন-শুধু বাটনে, যেখানে কোনো OCR-যোগ্য টেক্সট নেই) "
        "সরাসরি হাল ছেড়ে দিও না — locate_icon(বর্ণনা) দিয়ে vision-LLM ভিত্তিক fallback ট্রাই করো, "
        "যত সম্ভব স্পষ্ট/নির্দিষ্ট বর্ণনা দিয়ে (অবস্থান, রং, আকৃতি উল্লেখ করলে ভালো ফল হয়)।",
        "ডিসপ্লে/GUI নেই এমন হেডলেস সার্ভারে এই এজেন্ট কাজ করবে না — সেটা স্পষ্টভাবে জানিয়ে দাও।",
        "OCR/vision দুটোরই ফলাফল ভুল/অসম্পূর্ণ হতে পারে — নিশ্চিত না হলে সেটা উল্লেখ করো, এবং "
        "locate_icon-ও যদি 'not_found'/ভুল কোঅর্ডিনেট মনে হয় তাহলে ইউজারকে কীবোর্ড শর্টকাট বা "
        "মেনু-ভিত্তিক বিকল্প খুঁজতে বলো।",
    ],
    markdown=True,
    **MEMORY_KWARGS,
)
