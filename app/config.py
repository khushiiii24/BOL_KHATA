"""All settings come from the .env file in the project folder.

Only GNANI_API_KEY is required. Everything else has a sensible default.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _get(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


class Settings:
    def __init__(self) -> None:
        key = _get("GNANI_API_KEY")
        # The example file ships with a placeholder; treat it as "not set".
        self.gnani_key = "" if key.lower().startswith("paste") else key
        self.gnani_base = _get("GNANI_BASE_URL", "https://api.vachana.ai").rstrip("/")

        self.shop_name = _get("SHOP_NAME", "Apni Dukaan")

        # Gnani Prisma (speech -> text)
        self.stt_model = _get("STT_MODEL", "prisma-v3.0")

        # Gnani Timbre (text -> speech)
        self.tts_model = _get("TTS_MODEL", "timbre-v2.5")
        # One Gnani Timbre v2.5 voice per language (each v2.5 voice has a home language).
        # Change any of them in .env, e.g. TTS_VOICE_TA=Trisha
        defaults = {"hi": "Nalini", "en": "Kaveri", "mr": "Zahira", "gu": "Falak", "bn": "Kirra",
                    "ta": "Asmita", "te": "Lavanya", "kn": "Saanvi"}
        legacy = {"hi": _get("TTS_VOICE_HINDI"), "en": _get("TTS_VOICE_ENGLISH")}
        self.voices = {lang: _get(f"TTS_VOICE_{lang.upper()}") or legacy.get(lang) or voice
                       for lang, voice in defaults.items()}
        # Timbre v3.0 voices speak every language; use one voice for all if TTS_MODEL=timbre-v3.0
        if self.tts_model.lower() == "timbre-v3.0":
            v3 = _get("TTS_VOICE_V3", "Shivani")
            self.voices = {lang: _get(f"TTS_VOICE_{lang.upper()}") or v3 for lang in defaults}
        self.voice_hindi = self.voices["hi"]
        self.voice_english = self.voices["en"]

        # Optional: an LLM makes understanding smarter. Without it, the
        # built-in rule-based parser is used (works offline, no key needed).
        llm_key = _get("LLM_API_KEY")
        self.llm_key = "" if llm_key.lower().startswith("paste") else llm_key
        self.llm_base = _get("LLM_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
        self.llm_model = _get("LLM_MODEL", "llama-3.3-70b-versatile")

        # Sign in with Google (optional but recommended): every Gmail gets its own private khata.
        client_id = _get("GOOGLE_CLIENT_ID")
        self.google_client_id = "" if client_id.lower().startswith("paste") else client_id
        # Empty = anyone with a Google account can sign up. Or list Gmails (comma-separated) to invite only them.
        # (OWNER_EMAIL is the old name of this setting and still works.)
        self.allowed_emails = (_get("ALLOWED_EMAILS") or _get("OWNER_EMAIL")).lower()
        # Only when you put Bol Khata online: its https address, e.g. https://bolkhata.example.com
        # (then the sign-in cookie is only ever sent over https).
        self.public_url = _get("PUBLIC_URL").rstrip("/")

        # Where khatas are saved. On your laptop: the data folder. On Vercel the project folder is read-only,
        # so it uses /tmp, which Vercel wipes from time to time (fine for a demo, not for a real shop).
        data_dir = _get("DATA_DIR") or ("/tmp/bol-khata" if os.getenv("VERCEL") else str(ROOT / "data"))
        self.db_path = Path(data_dir) / "khata.db"
        # Signs the sign-in cookie. Set it when online (Vercel), so every server copy accepts the same cookie.
        self.session_secret = _get("SESSION_SECRET")

    @property
    def gnani_ready(self) -> bool:
        return bool(self.gnani_key)

    @property
    def llm_ready(self) -> bool:
        return bool(self.llm_key)


settings = Settings()
