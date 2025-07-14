from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
import os
import tempfile

# ✅ Custom modules
from gemini import generate_answer  # type: ignore
from database import SessionLocal, engine  # Add engine here
from models import ChatHistory, Base      # Add Base here to allow table creation

# ✅ Optional dependencies
try:
    from googletrans import Translator
except ImportError:
    Translator = None

try:
    from gtts import gTTS
except ImportError:
    gTTS = None

app = FastAPI(title="Hexa Bot API")

# ✅ CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Template directory
templates = Jinja2Templates(directory="templates")

# ✅ In-memory history
search_history = []

# ✅ Request Models
class TranslateRequest(BaseModel):
    text: str
    target_lang: str

class SpeakRequest(BaseModel):
    text: str
    lang: str = "en"

# ✅ Pre-warm Gemini and create tables
@app.on_event("startup")
async def warm_up_gemini():
    try:
        generate_answer("Hello")
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Startup failed: {e}")

# ✅ Homepage
@app.get("/", response_class=HTMLResponse)
async def serve_homepage(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/favicon.ico")
async def favicon():
    return ""

# ✅ Translation Endpoint
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

# ✅ Text-to-Speech Endpoint
@app.post("/speak")
def speak_text(req: SpeakRequest):
    if not gTTS:
        raise HTTPException(status_code=503, detail="gTTS not available.")
    try:
        tts = gTTS(text=req.text, lang=req.lang)
        temp_path = os.path.join(tempfile.gettempdir(), "hexa_output.mp3")
        tts.save(temp_path)
        with open(temp_path, "rb") as f:
            audio_data = f.read()
        os.remove(temp_path)
        return {"message": "Speech synthesis complete", "size": len(audio_data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Speech failed: {str(e)}")

# ✅ Ask Gemini and store in DB
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

# ✅ In-memory history
@app.get("/history")
def get_history():
    return {"history": list(reversed(search_history))}

# ✅ DB-backed chat history
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

# ✅ Render HTML view of DB chat history
@app.get("/history-page", response_class=HTMLResponse)
def history_page(request: Request):
    db: Session = SessionLocal()
    try:
        records = db.query(ChatHistory).order_by(ChatHistory.created_at.desc()).limit(10).all()
        return templates.TemplateResponse("history.html", {"request": request, "records": records})
    finally:
        db.close()
