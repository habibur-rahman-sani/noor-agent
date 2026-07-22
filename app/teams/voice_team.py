from agno.team.team import Team
from config import get_model, get_db, MEMORY_KWARGS
from agents.voice_agent import voice_agent

team = Team(
    name="Voice Team",
    mode="coordinate",
    model=get_model("general"),
    db=get_db(),
    members=[voice_agent],
    instructions=[
        "ডিভাইসের স্পিকারে সরাসরি জোরে বলার (text-to-speech playback) যেকোনো কাজ -> Voice Agent।",
        "ব্রাউজার UI-তে অডিও ইতিমধ্যে /api/tts দিয়ে হয় — এই টিম শুধু OS/হেডলেস-লেভেল ভয়েস আউটপুটের জন্য।",
    ],
    markdown=True,
    **MEMORY_KWARGS,
)
