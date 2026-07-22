"""
voice_daemon.py
================
"Jarvis" অভিজ্ঞতার মূল অংশ — মাইক্রোফোনে সবসময় কান পেতে থাকা, wake-word শুনলে
পরের কথাটা কমান্ড হিসেবে ধরে সুপারভাইজারকে পাঠানো, উত্তর স্পিকারে বলা।

এটা `server.py`-র (FastAPI/uvicorn) ভেতরে চলে না — কারণ মাইক ক্যাপচার ব্লকিং লুপ,
আর Whisper মডেল বেশ CPU-ভারী; আলাদা প্রসেস হিসেবে চালানো ভালো (আলাদা systemd
সার্ভিস — `deploy/linux/agno-voice.service.template`, ডিফল্টে বন্ধ থাকে কারণ এটা
রিসোর্স-ভারী, ইউজার ইচ্ছাকৃতভাবে চালু করবে)।

চালাও: python voice_daemon.py
(আগে server.py আলাদাভাবে চালু থাকতে হবে, কারণ এটা HTTP দিয়ে /api/chat আর
/api/tts কল করে — এতে করে voice_daemon.py মূল সার্ভারের কোড ইমপোর্ট করা লাগে না,
আলাদা প্রসেস/আলাদা রিস্টার্ট-চক্র রাখা সহজ হয়)।

নির্ভরতা: faster-whisper (STT), sounddevice + numpy (মাইক ক্যাপচার), requests।
সিস্টেমে PortAudio (libportaudio2) ইনস্টল থাকা লাগবে (install.sh এটা যোগ করে)।
"""
import io
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
import wave

import numpy as np
import requests
import sounddevice as sd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [voice-daemon] %(message)s")
logger = logging.getLogger("voice-daemon")

API_BASE = os.getenv("AGNO_API_BASE", "http://localhost:8000")
WAKE_WORDS = [w.strip().lower() for w in os.getenv("WAKE_WORDS", "hey agno,হে আগ্নো,জার্ভিস,jarvis").split(",") if w.strip()]
SAMPLE_RATE = int(os.getenv("MIC_SAMPLE_RATE", "16000"))
LISTEN_CHUNK_SECONDS = float(os.getenv("LISTEN_CHUNK_SECONDS", "4"))
COMMAND_SECONDS = float(os.getenv("COMMAND_SECONDS", "6"))
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "tiny")
SESSION_ID = "voice-daemon"


def _record(seconds: float) -> np.ndarray:
    frames = sd.rec(int(seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="int16")
    sd.wait()
    return frames


def _to_wav_bytes(frames: np.ndarray) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(frames.tobytes())
    return buf.getvalue()


def _play_wav_bytes(audio_bytes: bytes):
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio_bytes)
        path = f.name
    if shutil.which("aplay"):
        subprocess.run(["aplay", "-q", path], check=False)
    elif shutil.which("ffplay"):
        subprocess.run(["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path], check=False)
    else:
        logger.warning("কোনো অডিও-প্লেয়ার (aplay/ffplay) পাওয়া যায়নি — উত্তর বলা যাচ্ছে না, শুধু টেক্সট লগ হবে।")


def _play_beep():
    """সংক্ষিপ্ত একটা 'শুনছি' beep — নিজে থেকেই সাইন-ওয়েভ জেনারেট করে, বাইরের ফাইল লাগে না।"""
    try:
        t = np.linspace(0, 0.15, int(SAMPLE_RATE * 0.15), False)
        tone = (np.sin(880 * 2 * np.pi * t) * 3000).astype(np.int16)
        sd.play(tone, SAMPLE_RATE)
        sd.wait()
    except Exception:
        pass


def _load_whisper():
    from faster_whisper import WhisperModel
    logger.info("Whisper মডেল ('%s') লোড হচ্ছে (প্রথমবার ডাউনলোড হতে পারে)...", WHISPER_MODEL_SIZE)
    return WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")


def _transcribe(model, frames: np.ndarray) -> str:
    audio_f32 = frames.astype(np.float32).flatten() / 32768.0
    segments, _ = model.transcribe(audio_f32, language=None, vad_filter=True)
    return " ".join(seg.text for seg in segments).strip()


def _contains_wake_word(text: str) -> bool:
    low = text.lower()
    return any(w in low for w in WAKE_WORDS)


def _send_command(text: str) -> str:
    try:
        resp = requests.post(f"{API_BASE}/api/chat", json={"message": text, "session_id": SESSION_ID}, timeout=120)
        resp.raise_for_status()
        return resp.json().get("response", "")
    except Exception as e:  # noqa: BLE001
        return f"সার্ভারে পৌঁছানো যায়নি ({e}) — server.py চালু আছে কিনা, AGNO_API_BASE ঠিক আছে কিনা যাচাই করো।"


def _speak(text: str):
    try:
        resp = requests.post(f"{API_BASE}/api/tts", json={"text": text[:1000]}, timeout=60)
        resp.raise_for_status()
        _play_wav_bytes(resp.content)
    except Exception as e:  # noqa: BLE001
        logger.warning("TTS/প্লেব্যাক ব্যর্থ (%s) — উত্তর: %s", e, text[:200])


def main():
    logger.info("Wake-word: %s | Sample rate: %d | Model: %s", WAKE_WORDS, SAMPLE_RATE, WHISPER_MODEL_SIZE)
    try:
        model = _load_whisper()
    except Exception as e:  # noqa: BLE001
        logger.error("Whisper লোড ব্যর্থ (%s) — 'pip install faster-whisper' করা আছে কিনা যাচাই করো।", e)
        sys.exit(1)

    logger.info("শুনতে শুরু করেছি... (wake word বলো, যেমন 'Hey Agno' বা 'জার্ভিস')")
    while True:
        try:
            frames = _record(LISTEN_CHUNK_SECONDS)
            text = _transcribe(model, frames)
            if not text:
                continue
            if _contains_wake_word(text):
                logger.info("Wake word শোনা গেছে: '%s' — কমান্ড শুনছি...", text)
                _play_beep()
                cmd_frames = _record(COMMAND_SECONDS)
                command_text = _transcribe(model, cmd_frames)
                if not command_text:
                    logger.info("কোনো কমান্ড বোঝা যায়নি।")
                    continue
                logger.info("কমান্ড: %s", command_text)
                response_text = _send_command(command_text)
                logger.info("উত্তর: %s", response_text[:300])
                _speak(response_text)
        except KeyboardInterrupt:
            logger.info("বন্ধ করা হচ্ছে।")
            break
        except Exception as e:  # noqa: BLE001
            logger.exception("লুপে ত্রুটি, ২ সেকেন্ড পর আবার চেষ্টা: %s", e)
            time.sleep(2)


if __name__ == "__main__":
    main()
