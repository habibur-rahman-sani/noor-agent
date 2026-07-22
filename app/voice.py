"""
voice.py — Phase 2: ওপেন-সোর্স STT (স্পিচ-টু-টেক্সট) ও TTS (টেক্সট-টু-স্পিচ)
==============================================================================

STT: faster-whisper (Whisper মডেলের দ্রুত/হালকা ভার্সন) — বাংলা+ইংরেজি মিশ্রিত
     স্পিচও মোটামুটি ভালো ধরে।
TTS: Facebook-এর MMS-TTS (Massively Multilingual Speech) — বাংলার জন্য
     `facebook/mms-tts-ben`, ইংরেজির জন্য `facebook/mms-tts-eng`।
     ইনপুট টেক্সটে বাংলা ইউনিকোড থাকলে বাংলা মডেল, নাহলে ইংরেজি মডেল ব্যবহার হয়।

মডেলগুলো প্রথমবার ব্যবহারের সময় ডাউনলোড হয় (~কয়েকশো MB) এবং RAM-এ ক্যাশ থাকে
(lazy-loading — সার্ভার স্টার্ট হওয়ার সময় লোড হয় না, তাই বুট দ্রুত হয়)।

নোট: STT-র জন্য সিস্টেমে `ffmpeg` ইনস্টল থাকা লাগবে (audio decode করতে):
    sudo apt install ffmpeg
"""

import io
import re
import tempfile
import logging

logger = logging.getLogger("agno-voice")

_whisper_model = None
_tts_models: dict = {}  # lang code -> (model, tokenizer)

BENGALI_RE = re.compile(r"[\u0980-\u09FF]")


def _get_whisper():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        # "small" ভালো balance (accuracy vs speed); GPU থাকলে device="cuda", compute_type="float16" দাও
        _whisper_model = WhisperModel("small", device="cpu", compute_type="int8")
        logger.info("Whisper STT model loaded.")
    return _whisper_model


def _get_tts(lang: str):
    if lang not in _tts_models:
        from transformers import VitsModel, AutoTokenizer
        model_id = f"facebook/mms-tts-{lang}"
        model = VitsModel.from_pretrained(model_id)
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        _tts_models[lang] = (model, tokenizer)
        logger.info("TTS model loaded: %s", model_id)
    return _tts_models[lang]


def transcribe_audio(audio_bytes: bytes, suffix: str = ".webm") -> str:
    """ব্রাউজার থেকে আসা অডিও (webm/ogg/wav যেকোনো ফরম্যাট, ffmpeg দিয়ে ডিকোড হয়) টেক্সটে রূপান্তর করে।"""
    model = _get_whisper()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as f:
        f.write(audio_bytes)
        f.flush()
        segments, info = model.transcribe(f.name, language=None, vad_filter=True)
        text = "".join(seg.text for seg in segments).strip()
    return text


def synthesize_speech(text: str) -> tuple[bytes, int]:
    """
    টেক্সট থেকে WAV অডিও বাইট তৈরি করে (সাথে sample rate রিটার্ন করে)।
    টেক্সটে বাংলা অক্ষর থাকলে বাংলা কণ্ঠ, নাহলে ইংরেজি কণ্ঠ ব্যবহার হয়।
    """
    import torch
    import soundfile as sf

    lang = "ben" if BENGALI_RE.search(text) else "eng"
    model, tokenizer = _get_tts(lang)

    inputs = tokenizer(text, return_tensors="pt")
    with torch.no_grad():
        output = model(**inputs).waveform

    waveform = output.squeeze().cpu().numpy()
    sample_rate = model.config.sampling_rate

    buf = io.BytesIO()
    sf.write(buf, waveform, sample_rate, format="WAV")
    return buf.getvalue(), sample_rate
