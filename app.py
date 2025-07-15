from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
import os
import requests
from io import BytesIO

from gemini import generate_answer  # type: ignore
from database import SessionLocal, engine
from models import ChatHistory, Base

# Optional translation support
try:
    from googletrans import Translator
except ImportError:
    Translator = None

# Initialize FastAPI app
app = FastAPI(title="Hexa Bot API")

# Enable CORS (allow frontend requests)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Template rendering
templates = Jinja2Templates(directory=os.getenv("TEMPLATE_DIR", "templates"))

# In-memory search history
search_history = []

# ElevenLabs config
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel (default ElevenLabs voice)

# Request schemas
class TranslateRequest(BaseModel):
    text: str
    target_lang: str

class SpeakRequest(BaseModel):
    text: str
    lang: str = "en"

# App startup: warm up Gemini + create DB tables
@app.on_event("startup")
async def warm_up():
    try:
        generate_answer("Hello")
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Startup failed: {e}")

# Homepage
@app.get("/", response_class=HTMLResponse)
async def serve_homepage(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/favicon.ico")
async def favicon():
    return ""

# Translation
@app.post("/translate")
def translate_text(req: TranslateRequest):
    if not Translator:
        raise HTTPException(status_code=503, detail="Translation module not available.")
    try:
        translator = Translator()
        translated = translator.translate(req.text, dest=req.target_lang)
        return {"translated_text": translated.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Translation failed: {str(e)}")

# ElevenLabs Text-to-Speech (streaming for instant audio)
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
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.4,
                "similarity_boost": 0.75
            }
        }
        response = requests.post(url, headers=headers, json=payload, stream=True)
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"ElevenLabs error: {response.text}")

        return StreamingResponse(response.raw, media_type="audio/mpeg")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Speech synthesis failed: {str(e)}")

# Gemini response + store in DB
@app.get("/ask-gemini")
def ask_gemini_endpoint(q: str):
    try:
        answer = generate_answer(q)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini error: {e}")

    db: Session = SessionLocal()
    try:
        chat = ChatHistory(question=q, answer=answer)
        db.add(chat)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"DB error: {e}")
    finally:
        db.close()

    search_history.append(q)
    return {"answer": answer}

# In-memory history
@app.get("/history")
def get_history():
    return {"history": list(reversed(search_history))}

# DB-based chat history
@app.get("/db-history")
def get_db_history():
    db: Session = SessionLocal()
    try:
        records = db.query(ChatHistory).order_by(ChatHistory.created_at.desc()).limit(10).all()
        return [
            {
                "id": r.id,
                "question": r.question,
                "answer": r.answer,
                "timestamp": r.created_at
            } for r in records
        ]
    finally:
        db.close()

# HTML-rendered chat history page
@app.get("/history-page", response_class=HTMLResponse)
def history_page(request: Request):
    db: Session = SessionLocal()
    try:
        records = db.query(ChatHistory).order_by(ChatHistory.created_at.desc()).limit(10).all()
        return templates.TemplateResponse("history.html", {"request": request, "records": records})
    finally:
        db.close()
