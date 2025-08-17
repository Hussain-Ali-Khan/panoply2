from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
import os
import requests
from io import BytesIO
import traceback

from gemini import generate_answer  # type: ignore
from database import SessionLocal, engine
from models import ChatHistory, Base
from deep_translator import GoogleTranslator

app = FastAPI(title="Hexa Bot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory=os.getenv("TEMPLATE_DIR", "templates"))

search_history = []

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = "EXAVITQu4vr4xnSDxMaL"  # Rachel's actual ID

# ✅ Request Models
class TranslateRequest(BaseModel):
    text: str
    target_lang: str

class SpeakRequest(BaseModel):
    text: str
    lang: str = "en"

# ✅ Startup
@app.on_event("startup")
async def warm_up():
    try:
        generate_answer("Hello")
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Startup failed: {e}")

@app.get("/", response_class=HTMLResponse)
async def serve_homepage(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/favicon.ico")
async def favicon():
    return ""

# ✅ Translate endpoint
@app.post("/translate")
def translate_text(req: TranslateRequest):
    try:
        translated = GoogleTranslator(source='auto', target=req.target_lang).translate(req.text)
        return {"translated_text": translated}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Translation failed: {str(e)}")

# ✅ ElevenLabs speech synthesis
@app.post("/speak")
def speak_text(req: SpeakRequest):
    if not ELEVENLABS_API_KEY:
        raise HTTPException(status_code=503, detail="ElevenLabs API key not configured")

    try:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}/stream"
        headers = {
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json"
        }
        payload = {
            "text": req.text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }

        print(f"[DEBUG] Making request to ElevenLabs with: {payload}")
        response = requests.post(url, headers=headers, json=payload)

        if response.status_code != 200:
            print(f"[ERROR] ElevenLabs failed: {response.status_code}, {response.text}")
            raise HTTPException(status_code=500, detail=f"ElevenLabs error: {response.text}")

        audio_stream = BytesIO(response.content)
        return StreamingResponse(audio_stream, media_type="audio/mpeg")

    except Exception as e:
        print(f"[EXCEPTION] Error in ElevenLabs API: {e}")
        raise HTTPException(status_code=500, detail=f"Speech synthesis failed: {str(e)}")

# ✅ Ask Gemini endpoint (DB is optional now)
@app.get("/ask-gemini")
def ask_gemini_endpoint(q: str):
    try:
        answer = generate_answer(q)
    except Exception as e:
        error_trace = traceback.format_exc()
        print("🔥 Gemini error:", error_trace)
        raise HTTPException(status_code=500, detail=f"Gemini error: {e}")

    # Try saving to DB (non-blocking)
    try:
        db: Session = SessionLocal()
        chat = ChatHistory(question=q, answer=answer)
        db.add(chat)
        db.commit()
        db.close()
    except Exception as e:
        print("⚠️ History DB error (non-blocking):", e)

    search_history.append(q)
    return {"answer": answer}

@app.get("/history")
def get_history():
    return {"history": list(reversed(search_history))}

@app.get("/db-history")
def get_db_history():
    try:
        db: Session = SessionLocal()
        records = db.query(ChatHistory).order_by(ChatHistory.created_at.desc()).limit(10).all()
        db.close()
        return [
            {
                "id": r.id,
                "question": r.question,
                "answer": r.answer,
                "timestamp": r.created_at
            } for r in records
        ]
    except Exception as e:
        print("⚠️ DB history fetch failed:", e)
        return {"history": "Unavailable (DB issue)"}

@app.get("/history-page", response_class=HTMLResponse)
def history_page(request: Request):
    try:
        db: Session = SessionLocal()
        records = db.query(ChatHistory).order_by(ChatHistory.created_at.desc()).limit(10).all()
        db.close()
        return templates.TemplateResponse("history.html", {"request": request, "records": records})
    except Exception as e:
        print("⚠️ DB history page failed:", e)
        # return page but with no records
        return templates.TemplateResponse("history.html", {"request": request, "records": []})
