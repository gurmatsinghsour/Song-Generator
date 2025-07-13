from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.responses import FileResponse
import os

from generate_song import (
    load_tokenizer,
    load_latest_model,
    generate_with_local_model,
    generate_with_gemini,
    create_song_from_lyrics,
    genai,
)

app = FastAPI(title="AI Song Generator")

# Load resources once at startup
TOKENIZER = load_tokenizer()
MODEL = load_latest_model()
API_KEY = os.environ.get("GEMINI_API_KEY")

class Prompt(BaseModel):
    text: str
    max_words: int = 50

class Lyrics(BaseModel):
    lyrics: str
    model_name: str | None = None

@app.post("/generate")
def generate(prompt: Prompt):
    local = generate_with_local_model(prompt.text, TOKENIZER, MODEL, max_words=prompt.max_words)
    gemini_lyrics = None
    if API_KEY and genai:
        try:
            gemini_lyrics = generate_with_gemini(prompt.text, API_KEY)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))
    return {"local": local, "gemini": gemini_lyrics}

@app.post("/song")
def song(data: Lyrics):
    try:
        path = create_song_from_lyrics(data.lyrics)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return FileResponse(path, media_type="audio/mpeg", filename=os.path.basename(path))
