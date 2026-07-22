"""
Voice এজেন্ট — voice.py-র STT/TTS মডেল ব্যবহার করে ডিভাইসের স্পিকারে সরাসরি
কথা বলতে পারা (অন্য এজেন্ট/সুপারভাইজার এই এজেন্টকে "জোরে বলো" টাইপ কাজে ব্যবহার
করতে পারবে)। ব্রাউজার-ভিত্তিক STT/TTS (মাইক রেকর্ড -> টেক্সট, টেক্সট -> UI-তে অডিও)
এখনো server.py-র /api/stt ও /api/tts এন্ডপয়েন্ট দিয়েই হয় — এই এজেন্টটা তার
পাশাপাশি "ডিভাইসের স্পিকারে সরাসরি বলা" যোগ করে (headless/OS-লেভেল ব্যবহারের জন্য)।
"""
import shutil
import subprocess
import tempfile

from agno.agent import Agent
from agno.tools.toolkit import Toolkit
from config import get_model, get_db, MEMORY_KWARGS


class VoiceTools(Toolkit):
    """টেক্সট থেকে অডিও বানিয়ে ডিভাইসের স্পিকারে সরাসরি প্লে করার টুল।"""

    def __init__(self, **kwargs):
        super().__init__(name="voice_tools", tools=[self.speak], **kwargs)

    def speak(self, text: str) -> str:
        """দেওয়া টেক্সট ডিভাইসের স্পিকারে জোরে বলে (বাংলা/ইংরেজি অটো-ডিটেক্ট, voice.py-র MMS-TTS ব্যবহার করে)।

        Args:
            text: যা বলতে হবে
        """
        try:
            import voice as voice_module
            audio_bytes, sample_rate = voice_module.synthesize_speech(text)
        except Exception as e:  # noqa: BLE001
            return f"স্পিচ তৈরি ব্যর্থ হয়েছে ({e}) — voice.py-র dependency (torch, transformers, soundfile) ইনস্টল আছে কিনা যাচাই করো।"

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            path = f.name

        player_cmd = None
        if shutil.which("aplay"):
            player_cmd = ["aplay", path]
        elif shutil.which("ffplay"):
            player_cmd = ["ffplay", "-nodisp", "-autoexit", path]
        elif shutil.which("paplay"):
            player_cmd = ["paplay", path]

        if not player_cmd:
            return (
                f"অডিও তৈরি হয়েছে ({path}) কিন্তু কোনো অডিও-প্লেয়ার পাওয়া যায়নি — "
                "'sudo apt install alsa-utils' (aplay) অথবা 'sudo apt install pulseaudio-utils' "
                "(paplay) ইনস্টল করো।"
            )

        try:
            subprocess.run(player_cmd, check=False)
            return "বলা হয়ে গেছে।"
        except Exception as e:  # noqa: BLE001
            return f"অডিও প্লে ব্যর্থ হয়েছে ({e}), তবে ফাইল তৈরি হয়েছে: {path}"


voice_agent = Agent(
    name="Voice Agent",
    role="ডিভাইসের স্পিকারে সরাসরি টেক্সট জোরে বলা (OS-লেভেল ভয়েস আউটপুট)",
    model=get_model("general"),
    db=get_db(),
    tools=[VoiceTools()],
    instructions=[
        "যখন ইউজার/সুপারভাইজার বলে 'জোরে বলো' / 'স্পিকারে বাজাও' তখন speak টুল ব্যবহার করো।",
        "ব্রাউজার UI-তে টেক্সট রিপ্লাই এমনিতেই দেখানো হবে — এই এজেন্ট শুধু ডিভাইসের স্পিকারে "
        "অতিরিক্তভাবে জোরে বলার জন্য (headless/OS মোডে বিশেষভাবে দরকারি)।",
        "প্লেয়ার/মডেল না থাকলে সেই ত্রুটি ইউজারকে স্পষ্টভাবে জানাও।",
    ],
    markdown=True,
    **MEMORY_KWARGS,
)
