from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import tempfile

# ✅ Gemini answer generator
from gemini import generate_answer  # type: ignore

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
    allow_origins=["*"],  # Use ["http://localhost:8888"] for strict mode
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Template directory
templates = Jinja2Templates(directory="templates")

# ✅ In-memory search history
search_history = []

# ✅ Request Models
class TranslateRequest(BaseModel):
    text: str
    target_lang: str

class SpeakRequest(BaseModel):
    text: str
    lang: str = "en"

# ✅ Pre-warm Gemini (reduces cold start delay)
@app.on_event("startup")
async def warm_up_gemini():
    generate_answer("Hello")

# ✅ Homepage
@app.get("/", response_class=HTMLResponse)
async def serve_homepage(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# ✅ Suppress favicon errors
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

# ✅ Ask Gemini (main logic)
@app.get("/ask-gemini")
def ask_gemini_endpoint(q: str):
    search_history.append(q)
    answer = generate_answer(q)
    return {"answer": answer}

# ✅ View search history
@app.get("/history")
def get_history():
    return {"history": list(reversed(search_history))}
