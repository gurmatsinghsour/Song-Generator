import os
import re
import pickle
import numpy as np

from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.sequence import pad_sequences

# Optional imports for external services
try:
    import google.generativeai as genai
except ImportError:  # pragma: no cover - library optional
    genai = None

try:
    from audiocraft.models import MusicGen
    from audiocraft.data.audio import audio_write
except ImportError:  # pragma: no cover - library optional
    MusicGen = None
    audio_write = None

TOKENIZER_PATH = os.path.join("Tokenizer", "tokenizer.pkl")
MODELS_DIR = "Models"
DEFAULT_OUTPUT = "generated_song.mp3"


def load_tokenizer(path: str = TOKENIZER_PATH):
    """Load the saved tokenizer."""
    with open(path, "rb") as f:
        return pickle.load(f)


def load_latest_model(directory: str = MODELS_DIR):
    """Load the latest `.h5` model from the Models directory."""
    files = [f for f in os.listdir(directory) if f.endswith(".h5")]
    if not files:
        raise FileNotFoundError("No model files found in 'Models' directory")

    def version(fname: str) -> int:
        match = re.search(r"_v(\d+)", fname)
        return int(match.group(1)) if match else -1

    latest = max(files, key=version)
    model = load_model(os.path.join(directory, latest))
    return model


def generate_song_line(seed_text: str, tokenizer, model, next_words: int = 50) -> str:
    """Generate lyrics using the notebook-style loop provided by the user.

    Stops early if the model predicts an unknown token (``<OOV>``).
    """
    max_seq_len = model.input_shape[1] + 1
    for _ in range(next_words):
        token_list = tokenizer.texts_to_sequences([seed_text])[0]
        token_list = pad_sequences([token_list], maxlen=max_seq_len - 1, padding="pre")
        predicted = model.predict(token_list, verbose=0)
        output_word = tokenizer.index_word.get(int(np.argmax(predicted)))
        if not output_word or output_word == "<OOV>":
            break
        seed_text += " " + output_word
    return seed_text


def generate_with_local_model(prompt: str, tokenizer, model, max_words: int = 50) -> str:
    """Generate lyrics using the local model with padding."""
    return generate_song_line(prompt, tokenizer, model, next_words=max_words)


def generate_with_gemini(prompt: str, api_key: str, model_name: str = "gemini-pro") -> str:
    """Generate lyrics using the Gemini API."""
    if genai is None:
        raise RuntimeError("google-generativeai library is not installed")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    response = model.generate_content(prompt)
    return response.text.strip()


def create_song_from_lyrics(lyrics: str, output_path: str = DEFAULT_OUTPUT, model_name: str = "facebook/musicgen-small") -> str:
    """Generate an MP3 file from text lyrics using MusicGen."""
    if MusicGen is None or audio_write is None:
        raise RuntimeError("audiocraft library is required for music generation")

    musicgen = MusicGen.get_pretrained(model_name)
    wav = musicgen.generate([lyrics])[0]
    audio_write(output_path.split(".")[0], wav, musicgen.sample_rate, format="mp3")
    return output_path


