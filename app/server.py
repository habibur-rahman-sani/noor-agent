"""
server.py — Phase 1: CLI সিস্টেমকে সবসময়-চালু থাকা ওয়েব সার্ভারে রূপান্তর
=======================================================================

চালাও:
    uvicorn server:app --host 0.0.0.0 --port 8000

তারপর ব্রাউজারে খোলো:
    http://<সার্ভারের-আইপি>:8000

এই সার্ভারটা supervisor.py-র supervisor অবজেক্টকেই ব্যবহার করে —
teams/agents-এ কিছু বদলাতে হয়নি। UI বন্ধ করলেও, এই প্রসেসটা (uvicorn)
চালু থাকলে সিস্টেম কাজ চালিয়ে যাবে এবং MongoDB-তে সব সেভ হবে, তাই
পরে আবার UI খুললে আগের কথোপকথন ফিরে পাওয়া যাবে (session_id ধরে রাখলে)।

ব্যাকগ্রাউন্ডে ২৪/৭ চালু রাখতে (Linux):
    nohup uvicorn server:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &
বা প্রোডাকশনের জন্য systemd/Docker ব্যবহার করা ভালো (README_UI.md দ্যাখো)।
"""

import base64
import json
import secrets
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.requests import Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from supervisor import supervisor
from guardrail import list_pending_approvals, resolve_approval
from scheduler import start_scheduler
from auth import get_ui_credentials
import memory_core

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agno-server")

app = FastAPI(title="Agno Supervisor API")

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ---------------------------------------------------------------- auth ---
# আগে এই সার্ভার 0.0.0.0-এ কোনো লগইন ছাড়াই চলত — একই নেটওয়ার্কে থাকা যে কেউ
# এজেন্টের সাথে (সিস্টেম-লেভেল কন্ট্রোলসহ) সরাসরি কথা বলতে পারত। এখন সব রুট
# (health-check বাদে) HTTP Basic Auth দিয়ে সুরক্ষিত — বিস্তারিত: auth.py
_UI_USERNAME, _UI_PASSWORD = get_ui_credentials()
_PUBLIC_PATHS = {"/api/health"}


def _basic_auth_ok(header_value: str | None) -> bool:
    if not header_value or not header_value.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(header_value[len("Basic "):]).decode("utf-8")
        user, _, pw = decoded.partition(":")
    except Exception:
        return False
    # timing-safe compare — ক্যারেক্টার-বাই-ক্যারেক্টার টাইমিং দিয়ে পাসওয়ার্ড অনুমান ঠেকাতে
    return secrets.compare_digest(user, _UI_USERNAME) and secrets.compare_digest(pw, _UI_PASSWORD)


class BasicAuthMiddleware(BaseHTTPMiddleware):
    """সব HTTP রুট প্রোটেক্ট করে (স্ট্যাটিক ফাইলসহ)। নোট: Starlette-এর
    BaseHTTPMiddleware WebSocket স্কোপ ছুঁয়ে দেখে না, তাই /ws/chat আলাদাভাবে
    নিজের ভেতরেই (নিচে) একই চেক করে।"""

    async def dispatch(self, request: Request, call_next):
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)
        if _basic_auth_ok(request.headers.get("authorization")):
            return await call_next(request)
        return Response(
            status_code=401,
            content="Unauthorized",
            headers={"WWW-Authenticate": 'Basic realm="Agno System"'},
        )


app.add_middleware(BasicAuthMiddleware)


@app.on_event("startup")
async def _on_startup():
    """AI OS-এর 'proactive layer' চালু করে — শিডিউল করা কাজগুলো MongoDB
    job-store থেকে লোড হয়ে ব্যাকগ্রাউন্ডে চলতে শুরু করবে। ব্যর্থ হলেও
    (যেমন apscheduler ইনস্টল করা না থাকলে) সার্ভার চালু হতে বাধা দেয় না।"""
    try:
        start_scheduler()
    except Exception:
        logger.exception("Scheduler চালু করা যায়নি — 'pip install apscheduler' করা আছে কিনা যাচাই করো।")
        return
    try:
        from scheduler import get_scheduler
        memory_core.register_internal_jobs(get_scheduler())
    except Exception:
        logger.exception("মেমোরি-সামারাইজেশন জব রেজিস্টার করা যায়নি — সার্ভার চালু হতে বাধা দেয়নি।")


def _log_trace(session_id: str, message: str, response_text: str, teams_touched: list[str]):
    """Observability — প্রতিটা চ্যাট-এক্সচেঞ্জ MongoDB-তে লগ হয় (কোন টিম কতবার ব্যবহার
    হলো, কতটা লম্বা উত্তর এলো ইত্যাদি ডিবাগ/অপ্টিমাইজেশনের জন্য)।"""
    try:
        import os
        from pymongo import MongoClient
        db = MongoClient(os.getenv("MONGODB_URI", "mongodb://localhost:27017"))[
            os.getenv("MONGODB_DB_NAME", "agno_system")
        ]
        db["agno_traces"].insert_one({
            "session_id": session_id,
            "message": message[:2000],
            "response_length": len(response_text),
            "teams_touched": list(set(teams_touched)),
            "at": datetime.now(timezone.utc),
        })
    except Exception:
        pass  # ট্রেসিং ব্যর্থ হলেও চ্যাট আটকাবে না


# ---------------------------------------------------------------- helpers ---

def _extract_text(event) -> str:
    """
    Agno-র স্ট্রিমিং ইভেন্ট অবজেক্ট থেকে টেক্সট বের করার চেষ্টা করে।
    Agno-র ভার্সনভেদে event-এর শেপ একটু বদলাতে পারে, তাই কয়েকটা
    সম্ভাব্য attribute ধারাবাহিকভাবে চেক করা হচ্ছে যাতে ভার্সন আপগ্রেডে
    সার্ভার ক্র্যাশ না করে।
    """
    for attr in ("content", "text", "delta"):
        val = getattr(event, attr, None)
        if isinstance(val, str) and val:
            return val
    # কিছু ইভেন্ট টাইপ (tool_call ইত্যাদি) টেক্সট না — সেগুলো স্কিপ করা হয়
    return ""


def _team_label(event) -> str | None:
    """কোন Team/Agent উত্তর দিচ্ছে সেটা বের করার চেষ্টা (UI-তে badge দেখানোর জন্য)।"""
    for attr in ("agent_name", "team_name", "member_name"):
        val = getattr(event, attr, None)
        if isinstance(val, str) and val:
            return val
    return None


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


# ------------------------------------------------------------------ routes --

@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "teams": [t.name for t in supervisor.members],
    }


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """
    নন-স্ট্রিমিং সিম্পল এন্ডপয়েন্ট (কার্ল/স্ক্রিপ্ট দিয়ে টেস্ট করার জন্য সুবিধাজনক)।
    UI মূলত নিচের WebSocket এন্ডপয়েন্ট ব্যবহার করে (স্ট্রিমিং রেসপন্সের জন্য)।
    """
    session_id = req.session_id or str(uuid.uuid4())
    response = await supervisor.arun(req.message, session_id=session_id)
    text = getattr(response, "content", None) or str(response)
    memory_core.log_exchange(session_id, req.message, text)
    return {"session_id": session_id, "response": text}


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """
    HTTP স্ট্রিমিং চ্যাট (NDJSON) — ব্রাউজার fetch() দিয়ে পড়ে, তাই HTTP Basic Auth
    আপনাআপনি যায় (WebSocket-এ ব্রাউজার Authorization header পাঠাতে পারে না বলে
    আগের /ws/chat ব্রাউজারে কাজ করত না — এটা সেই সমস্যা এড়ায়)।

    প্রতিটা লাইন একটা JSON:
        {"type":"session","session_id":...}
        {"type":"chunk","text":"...","team":"..."}
        {"type":"done"}   |   {"type":"error","message":"..."}
    """
    session_id = req.session_id or str(uuid.uuid4())
    message = req.message

    async def gen():
        yield json.dumps({"type": "session", "session_id": session_id}) + "\n"
        parts: list[str] = []
        teams_touched: list[str] = []
        try:
            stream = await supervisor.arun(message, session_id=session_id, stream=True)
            async for event in stream:
                text = _extract_text(event)
                if not text:
                    continue
                team = _team_label(event)
                parts.append(text)
                if team:
                    teams_touched.append(team)
                yield json.dumps({"type": "chunk", "text": text, "team": team}) + "\n"
            # স্ট্রিম থেকে কোনো টেক্সট না এলে non-streaming fallback (যাতে উত্তর নিশ্চিত আসে)
            if not parts:
                response = await supervisor.arun(message, session_id=session_id)
                text = getattr(response, "content", None) or str(response)
                parts.append(text)
                yield json.dumps({"type": "chunk", "text": text, "team": None}) + "\n"
            yield json.dumps({"type": "done"}) + "\n"
        except Exception as e:  # noqa: BLE001 — স্ট্রিমিং ব্যর্থ হলে non-streaming fallback
            logger.warning("Streaming failed (%s), falling back.", e)
            try:
                response = await supervisor.arun(message, session_id=session_id)
                text = getattr(response, "content", None) or str(response)
                parts.append(text)
                yield json.dumps({"type": "chunk", "text": text, "team": None}) + "\n"
                yield json.dumps({"type": "done"}) + "\n"
            except Exception as e2:  # noqa: BLE001
                logger.exception("Fallback run failed too.")
                yield json.dumps({"type": "error", "message": str(e2)}) + "\n"
                return
        full = "".join(parts)
        _log_trace(session_id, message, full, teams_touched)
        memory_core.log_exchange(session_id, message, full)

    return StreamingResponse(gen(), media_type="application/x-ndjson")


@app.get("/api/sessions")
async def list_sessions(limit: int = 50):
    """অতীতের চ্যাট-সেশনের তালিকা (হিস্টরি সাইডবারের জন্য) — প্রতিটার প্রথম মেসেজ
    টাইটেল হিসেবে, সাম্প্রতিকতম আগে।"""
    try:
        import os
        from pymongo import MongoClient
        db = MongoClient(os.getenv("MONGODB_URI", "mongodb://localhost:27017"))[
            os.getenv("MONGODB_DB_NAME", "agno_system")
        ]
        pipeline = [
            {"$sort": {"at": 1}},
            {"$group": {
                "_id": "$session_id",
                "title": {"$first": "$user_message"},
                "last": {"$max": "$at"},
                "count": {"$sum": 1},
            }},
            {"$sort": {"last": -1}},
            {"$limit": limit},
        ]
        out = []
        for d in db["agno_conversation_log"].aggregate(pipeline):
            out.append({
                "session_id": d["_id"],
                "title": (d.get("title") or "")[:80],
                "last": d["last"].isoformat() if hasattr(d.get("last"), "isoformat") else str(d.get("last")),
                "count": d.get("count", 0),
            })
        return {"sessions": out}
    except Exception as e:  # noqa: BLE001
        return {"sessions": [], "error": str(e)}


@app.get("/api/history/{session_id}")
async def get_history(session_id: str, limit: int = 200):
    """একটা সেশনের সব মেসেজ (ইউজার + সিস্টেম), পুরনো থেকে নতুন ক্রমে।"""
    try:
        import os
        from pymongo import MongoClient
        db = MongoClient(os.getenv("MONGODB_URI", "mongodb://localhost:27017"))[
            os.getenv("MONGODB_DB_NAME", "agno_system")
        ]
        msgs = []
        for d in db["agno_conversation_log"].find(
            {"session_id": session_id}, {"_id": 0}
        ).sort("at", 1).limit(limit):
            msgs.append({
                "user_message": d.get("user_message", ""),
                "response_text": d.get("response_text", ""),
                "at": d["at"].isoformat() if hasattr(d.get("at"), "isoformat") else str(d.get("at")),
            })
        return {"session_id": session_id, "messages": msgs}
    except Exception as e:  # noqa: BLE001
        return {"session_id": session_id, "messages": [], "error": str(e)}


class TTSRequest(BaseModel):
    text: str


@app.post("/api/stt")
async def stt(audio: UploadFile = File(...)):
    """
    ব্রাউজার থেকে রেকর্ড করা অডিও পাঠালে টেক্সট রিটার্ন করে।
    মডেল প্রথমবার ব্যবহারের সময় ডাউনলোড হবে (একটু সময় লাগবে), পরে ক্যাশ থেকে দ্রুত চলবে।
    """
    try:
        import voice
        audio_bytes = await audio.read()
        suffix = "." + (audio.filename.rsplit(".", 1)[-1] if audio.filename and "." in audio.filename else "webm")
        text = voice.transcribe_audio(audio_bytes, suffix=suffix)
        return {"text": text}
    except Exception as e:  # noqa: BLE001
        logger.exception("STT failed")
        raise HTTPException(status_code=500, detail=f"স্পিচ-টু-টেক্সট ব্যর্থ: {e}")


@app.post("/api/tts")
async def tts(req: TTSRequest):
    """টেক্সট থেকে WAV অডিও ফিরিয়ে দেয় (Bengali/English অটো-ডিটেক্ট)।"""
    try:
        import voice
        if not req.text.strip():
            raise HTTPException(status_code=400, detail="খালি টেক্সট")
        audio_bytes, sample_rate = voice.synthesize_speech(req.text)
        return Response(content=audio_bytes, media_type="audio/wav")
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.exception("TTS failed")
        raise HTTPException(status_code=500, detail=f"টেক্সট-টু-স্পিচ ব্যর্থ: {e}")


@app.get("/api/approvals")
async def get_approvals():
    """এই মুহূর্তে কোন কোন ঝুঁকিপূর্ণ action মানুষের অনুমোদনের অপেক্ষায় আছে।"""
    return {"pending": list_pending_approvals()}


class ApprovalResponse(BaseModel):
    approved: bool


@app.post("/api/approvals/{request_id}/respond")
async def respond_approval(request_id: str, body: ApprovalResponse):
    """UI থেকে কোনো pending approval-request approve/deny করা।"""
    ok = resolve_approval(request_id, body.approved)
    if not ok:
        raise HTTPException(status_code=404, detail="এই approval-request পাওয়া যায়নি (হয়তো ইতিমধ্যে টাইমআউট হয়ে গেছে)।")
    return {"status": "approved" if body.approved else "denied"}


@app.get("/dashboard")
async def dashboard():
    return FileResponse(str(STATIC_DIR / "dashboard.html"))


@app.get("/api/traces")
async def get_traces(limit: int = 50):
    """সাম্প্রতিক চ্যাট-এক্সচেঞ্জের ট্রেস (কোন টিম কতবার ব্যবহার হলো ইত্যাদি) — observability dashboard-এর জন্য।"""
    try:
        import os
        from pymongo import MongoClient
        db = MongoClient(os.getenv("MONGODB_URI", "mongodb://localhost:27017"))[
            os.getenv("MONGODB_DB_NAME", "agno_system")
        ]
        docs = list(db["agno_traces"].find({}, {"_id": 0}).sort("at", -1).limit(limit))
        for d in docs:
            d["at"] = d["at"].isoformat() if hasattr(d.get("at"), "isoformat") else str(d.get("at"))
        return {"traces": docs}
    except Exception as e:  # noqa: BLE001
        return {"traces": [], "error": str(e)}


@app.get("/api/scheduler/results")
async def get_scheduler_results(limit: int = 50):
    """সাম্প্রতিক শিডিউল-করা কাজের ফলাফল — observability dashboard-এর জন্য।"""
    try:
        import os
        from pymongo import MongoClient
        db = MongoClient(os.getenv("MONGODB_URI", "mongodb://localhost:27017"))[
            os.getenv("MONGODB_DB_NAME", "agno_system")
        ]
        docs = list(db["agno_scheduler_results"].find({}, {"_id": 0}).sort("ran_at", -1).limit(limit))
        for d in docs:
            d["ran_at"] = d["ran_at"].isoformat() if hasattr(d.get("ran_at"), "isoformat") else str(d.get("ran_at"))
        return {"results": docs}
    except Exception as e:  # noqa: BLE001
        return {"results": [], "error": str(e)}


@app.get("/api/approvals/history")
async def get_approval_history(limit: int = 50):
    """অতীতের approve/deny/timeout হওয়া approval-request-এর audit log।"""
    try:
        import os
        from pymongo import MongoClient
        db = MongoClient(os.getenv("MONGODB_URI", "mongodb://localhost:27017"))[
            os.getenv("MONGODB_DB_NAME", "agno_system")
        ]
        docs = list(db["agno_approvals"].find({}).sort("created_at", -1).limit(limit))
        for d in docs:
            d["_id"] = str(d["_id"])
            for k in ("created_at", "resolved_at"):
                if hasattr(d.get(k), "isoformat"):
                    d[k] = d[k].isoformat()
        return {"approvals": docs}
    except Exception as e:  # noqa: BLE001
        return {"approvals": [], "error": str(e)}


@app.websocket("/ws/chat")
async def ws_chat(ws: WebSocket):
    """
    স্ট্রিমিং চ্যাট। ক্লায়েন্ট JSON পাঠাবে: {"message": "...", "session_id": "..."}
    সার্ভার প্রতিটা চাংক পাঠাবে: {"type": "chunk", "text": "...", "team": "..."}
    শেষে: {"type": "done"}  |  এরর হলে: {"type": "error", "message": "..."}
    """
    if not _basic_auth_ok(ws.headers.get("authorization")):
        await ws.close(code=4401, reason="Unauthorized")
        return
    await ws.accept()
    session_id = str(uuid.uuid4())
    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            message = data.get("message", "")
            session_id = data.get("session_id") or session_id
            if not message.strip():
                continue

            await ws.send_text(json.dumps({"type": "session", "session_id": session_id}))

            full_text_parts: list[str] = []
            teams_touched: list[str] = []
            try:
                stream = await supervisor.arun(message, session_id=session_id, stream=True)
                async for event in stream:
                    text = _extract_text(event)
                    if not text:
                        continue
                    team = _team_label(event)
                    full_text_parts.append(text)
                    if team:
                        teams_touched.append(team)
                    await ws.send_text(json.dumps({
                        "type": "chunk",
                        "text": text,
                        "team": team,
                    }))
                await ws.send_text(json.dumps({"type": "done"}))
                _log_trace(session_id, message, "".join(full_text_parts), teams_touched)
                memory_core.log_exchange(session_id, message, "".join(full_text_parts))
            except Exception as e:  # noqa: BLE001 — স্ট্রিমিং ব্যর্থ হলে non-streaming fallback
                logger.warning("Streaming failed (%s), falling back to non-streaming run.", e)
                try:
                    response = await supervisor.arun(message, session_id=session_id)
                    text = getattr(response, "content", None) or str(response)
                    await ws.send_text(json.dumps({"type": "chunk", "text": text, "team": None}))
                    await ws.send_text(json.dumps({"type": "done"}))
                    _log_trace(session_id, message, text, [])
                    memory_core.log_exchange(session_id, message, text)
                except Exception as e2:  # noqa: BLE001
                    logger.exception("Fallback run failed too.")
                    await ws.send_text(json.dumps({"type": "error", "message": str(e2)}))

    except WebSocketDisconnect:
        logger.info("Client disconnected (session=%s)", session_id)
