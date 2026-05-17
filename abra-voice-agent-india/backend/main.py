import os
import json
import time
import hashlib
import asyncio
import csv
import io
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from gtts import gTTS
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

load_dotenv()

app = FastAPI(title="Abra Voice Agent")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
Path("/tmp/tts_cache").mkdir(parents=True, exist_ok=True)
app.mount("/audio", StaticFiles(directory="/tmp/tts_cache"), name="audio")

call_sessions: dict = {}

def get_sheet():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_file("config/google-credentials.json", scopes=scope)
        client = gspread.authorize(creds)
        return client.open_by_key(os.getenv("GOOGLE_SHEET_ID")).worksheet("Leads")
    except Exception as e:
        print(f"⚠️ Sheet not available: {e}")
        return None

async def append_lead(lead: dict):
    print(f"📋 Lead: {lead}")
    try:
        sheet = get_sheet()
        if sheet is None:
            return
        sheet.append_row([
            datetime.now().strftime("%d/%m/%Y %H:%M"),
            lead.get("phone", ""), lead.get("name", ""), lead.get("company", ""),
            lead.get("interested", "Unknown"), lead.get("callback_time", ""),
            lead.get("duration", ""), lead.get("summary", ""),
        ])
        print(f"✅ Lead saved: {lead.get('phone')}")
    except Exception as e:
        print(f"❌ Sheets error: {e}")

def text_to_speech_url(text: str) -> str:
    cache_key = hashlib.md5(text.encode()).hexdigest()
    file_path = f"/tmp/tts_cache/{cache_key}.mp3"
    if not Path(file_path).exists():
        tts = gTTS(text=text, lang="en", tld="co.in")
        tts.save(file_path)
    return f"{os.getenv('BASE_URL')}/audio/{cache_key}.mp3"

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
SYSTEM_PROMPT = """You are Priya, a friendly outbound voice agent for Abra Logistics — a Bengaluru-based company offering road freight, air cargo, sea freight, and e-commerce delivery across India and internationally.

Your goals on this call:
1. Introduce Abra Logistics warmly
2. Ask if they need logistics/shipping services
3. If interested → collect: name, company, best callback time (ask ONE question at a time)
4. If not interested → thank them and end call

STRICT rules:
- Ask ONLY ONE question per response
- Wait for answer before asking next question
- Collect name FIRST, then company, then callback time
- Only set end_call true AFTER you have collected name AND said goodbye
- NEVER end call in the middle of collecting information
- Keep replies under 25 words
- ALWAYS respond in valid JSON only:
{
  "speech": "what to say out loud",
  "lead": {"name": "", "company": "", "interested": "Yes/No", "callback_time": ""},
  "end_call": false
}"""
async def get_ai_response(call_sid: str, user_speech: str) -> dict:
    session = call_sessions.setdefault(call_sid, {"history": [], "lead": {}, "start": time.time()})
    session["history"].append({"role": "user", "content": user_speech})
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + session["history"]
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            GROQ_API_URL,
            headers={"Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}", "Content-Type": "application/json"},
            json={"model": "llama-3.3-70b-versatile", "messages": messages, "max_tokens": 200, "temperature": 0.7},
        )
        result = resp.json()
    raw = result["choices"][0]["message"]["content"].strip()
    try:
        parsed = json.loads(raw.replace("```json", "").replace("```", "").strip())
    except Exception:
        parsed = {"speech": raw, "lead": {}, "end_call": False}
    session["lead"].update({k: v for k, v in parsed.get("lead", {}).items() if v})
    session["history"].append({"role": "assistant", "content": parsed["speech"]})
    return parsed

async def twilio_call(phone: str):
    url = f"https://api.twilio.com/2010-04-01/Accounts/{os.getenv('TWILIO_SID')}/Calls.json"
    data = {
        "To": phone, "From": os.getenv("TWILIO_NUMBER"),
        "Url": f"{os.getenv('BASE_URL')}/webhook/call-start",
        "StatusCallback": f"{os.getenv('BASE_URL')}/webhook/call-status",
        "StatusCallbackEvent": "completed no-answer busy failed", "Timeout": "30",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, data=data, auth=(os.getenv("TWILIO_SID"), os.getenv("TWILIO_TOKEN")))
        return resp.json()

@app.post("/webhook/call-start")
async def call_start(request: Request):
    form = await request.form()
    call_sid = form.get("CallSid", "unknown")
    phone = form.get("To", "")
    call_sessions[call_sid] = {"history": [], "lead": {"phone": phone}, "start": time.time()}
    opening = "Hello! This is Priya calling from Abra Logistics, a Bengaluru-based shipping and logistics company. Do you have a moment to hear about our services?"
    call_sessions[call_sid]["history"].append({"role": "assistant", "content": opening})
    audio_url = text_to_speech_url(opening)
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>{audio_url}</Play>
  <Gather input="speech" action="{os.getenv('BASE_URL')}/webhook/gather" method="POST" speechTimeout="5" timeout="8" language="en-IN"></Gather>
</Response>"""
    return Response(content=xml, media_type="application/xml")

@app.post("/webhook/gather")
async def gather(request: Request):
    form = await request.form()
    call_sid = form.get("CallSid", "unknown")
    speech = form.get("SpeechResult", "yes")
    try:
        ai = await get_ai_response(call_sid, speech or "yes")
        session = call_sessions.get(call_sid, {})
        audio_url = text_to_speech_url(ai["speech"])
        if ai.get("end_call"):
            duration = int(time.time() - session.get("start", time.time()))
            history_text = " | ".join(f"{h['role']}: {h['content']}" for h in session.get("history", []))
            await append_lead({**session.get("lead", {}), "duration": f"{duration}s", "summary": history_text})
            call_sessions.pop(call_sid, None)
            xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response><Play>{audio_url}</Play><Hangup/></Response>"""
        else:
            xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>{audio_url}</Play>
  <Gather input="speech" action="{os.getenv('BASE_URL')}/webhook/gather" method="POST" speechTimeout="auto" timeout="5" language="en-IN"></Gather>
</Response>"""
    except Exception as e:
        print(f"Error: {e}")
        sorry_url = text_to_speech_url("I apologize for the trouble. Our team will call you back. Thank you!")
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response><Play>{sorry_url}</Play><Hangup/></Response>"""
    return Response(content=xml, media_type="application/xml")

@app.post("/webhook/call-status")
async def call_status(request: Request):
    form = await request.form()
    call_sid = form.get("CallSid", "")
    status = form.get("CallStatus", "")
    phone = form.get("To", "")
    duration = form.get("CallDuration", "0")
    if status in ("no-answer", "busy", "failed", "canceled"):
        await append_lead({"phone": phone, "interested": "No Answer", "duration": f"{duration}s", "summary": f"Call status: {status}"})
        call_sessions.pop(call_sid, None)
    return JSONResponse({"ok": True})

@app.post("/api/call")
async def single_call(request: Request):
    body = await request.json()
    phone = body.get("phone", "").strip()
    if not phone:
        return JSONResponse({"error": "Phone number required"}, status_code=400)
    try:
        result = await twilio_call(phone)
        return {"success": True, "phone": phone, "sid": result.get("sid")}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def run_campaign(numbers: list, delay: int):
    for i, phone in enumerate(numbers):
        try:
            await twilio_call(phone)
            print(f"📞 Called {phone} ({i+1}/{len(numbers)})")
        except Exception as e:
            print(f"❌ Failed {phone}: {e}")
        await asyncio.sleep(delay)

@app.post("/api/campaign")
async def campaign(background_tasks: BackgroundTasks, file: UploadFile = File(...), delay_seconds: int = Form(5)):
    content = await file.read()
    reader = csv.DictReader(io.StringIO(content.decode("utf-8")))
    numbers = [row.get("phone") or row.get("Phone") or "" for row in reader]
    numbers = [n.strip() for n in numbers if n.strip()]
    if not numbers:
        return JSONResponse({"error": "No phone numbers found"}, status_code=400)
    background_tasks.add_task(run_campaign, numbers, delay_seconds)
    return {"success": True, "total": len(numbers)}

@app.get("/api/leads")
async def get_leads():
    try:
        sheet = get_sheet()
        if sheet is None:
            return {"leads": []}
        rows = sheet.get_all_records()
        return {"leads": rows}
    except Exception as e:
        return {"leads": []}

@app.get("/api/stats")
async def get_stats():
    try:
        sheet = get_sheet()
        if sheet is None:
            return {"total": 0, "interested": 0, "noAnswer": 0, "declined": 0, "conversionRate": 0}
        rows = sheet.get_all_records()
        total = len(rows)
        interested = sum(1 for r in rows if r.get("Interested") == "Yes")
        no_answer = sum(1 for r in rows if r.get("Interested") == "No Answer")
        declined = sum(1 for r in rows if r.get("Interested") == "No")
        rate = round((interested / total * 100), 1) if total else 0
        return {"total": total, "interested": interested, "noAnswer": no_answer, "declined": declined, "conversionRate": rate}
    except Exception as e:
        return {"total": 0, "interested": 0, "noAnswer": 0, "declined": 0, "conversionRate": 0}

@app.get("/health")
async def health():
    return {"status": "ok", "service": "Abra Voice Agent"}

scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")

async def daily_campaign():
    print("⏰ Daily campaign starting...")
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_file("config/google-credentials.json", scopes=scope)
        client = gspread.authorize(creds)
        numbers_sheet = client.open_by_key(os.getenv("GOOGLE_SHEET_ID")).worksheet("Numbers")
        rows = numbers_sheet.get_all_records()
        pending = [r["phone"] for r in rows if r.get("phone") and r.get("status", "").lower() != "called"]
        print(f"📋 {len(pending)} pending numbers")
        await run_campaign(pending, delay_seconds=8)
    except Exception as e:
        print(f"❌ Daily campaign error: {e}")

scheduler.add_job(daily_campaign, "cron", hour=10, minute=0)

@app.on_event("startup")
async def start_scheduler():
    scheduler.start()
    print("⏰ Scheduler started — daily calls at 10 AM IST")