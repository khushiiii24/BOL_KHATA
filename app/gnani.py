"""Talking to Gnani AI.

  Prisma  (speech -> text) : POST https://api.vachana.ai/stt/v3
  Timbre  (text -> speech) : POST https://api.vachana.ai/api/v1/tts/inference

Both need the header  X-API-Key-ID: <your key from app.gnani.ai>
Docs: https://docs.gnani.ai
"""

from __future__ import annotations

import json
from collections import OrderedDict

import requests

from .config import settings


class GnaniError(Exception):
    pass


# Prisma v3.0 can be told what the audio is about. This helps it hear
# names, items and amounts correctly.
STT_TOPIC = (
    "A small kirana shop owner in India is speaking udhaar khata (credit ledger) entries: "
    "customer names, items like atta, chawal, daal, tel, cheeni, doodh, and rupee amounts "
    "given on credit (udhaar) or received back (jama)."
)
STT_KEYTERMS = ["उधार", "जमा", "बाकी", "हिसाब", "रुपये", "udhaar", "jama", "baaki", "hisaab"]

# Retry with simpler settings only for these "setting not accepted" errors.
_RETRY_TYPES = {"INVALID_MODEL", "INVALID_CONTEXT", "INVALID_FORMAT", "INVALID_LANGUAGE_CODE",
                "INVALID_KEYTERMS", "VALIDATION_ERROR"}

_HINTS = {
    401: "Your Gnani API key is wrong or missing. Check GNANI_API_KEY in the .env file.",
    402: "Your Gnani credits may be used up. Check usage on app.gnani.ai.",
    403: "This Gnani key is not allowed to use this API.",
    429: "Too many requests. Wait a few seconds and try again.",
}


def _error_info(resp: requests.Response) -> tuple[str, str]:
    """Returns (error_type, message) from any of Gnani's error shapes."""
    try:
        body = resp.json()
    except ValueError:
        return "", resp.text[:200]
    etype, msg = "", ""
    if isinstance(body, dict):
        err, detail = body.get("error"), body.get("detail")
        if isinstance(err, dict):
            etype, msg = err.get("type", ""), err.get("message", "")
        if isinstance(detail, dict):
            etype = etype or detail.get("error_code", "")
            msg = msg or detail.get("message", "")
        elif isinstance(detail, list):
            etype = etype or "VALIDATION_ERROR"
            msg = msg or "; ".join(str(d.get("msg", d)) for d in detail[:3] if isinstance(d, dict))
        elif isinstance(detail, str):
            msg = msg or detail
        msg = msg or body.get("message", "")
    return etype, msg


def _raise(resp: requests.Response, what: str):
    etype, msg = _error_info(resp)
    hint = _HINTS.get(resp.status_code, "")
    raise GnaniError(f"Gnani {what} error {resp.status_code} {etype}: {msg} {hint}".strip())


def transcribe(audio: bytes, filename: str = "speech.wav", language: str = "hi-IN",
               names: list[str] | None = None) -> dict:
    """Send recorded audio to Gnani Prisma and get the text back."""
    if not settings.gnani_ready:
        raise GnaniError("Gnani API key not found. Put GNANI_API_KEY in the .env file and restart.")

    url = f"{settings.gnani_base}/stt/v3"
    headers = {"X-API-Key-ID": settings.gnani_key}
    single_language = language.split(",")[0] if language != "indic-auto" else "hi-IN"

    attempts = []
    if settings.stt_model.lower() == "prisma-v3.0":
        keyterms = (names or [])[:150] + STT_KEYTERMS
        attempts.append({"model": "prisma-v3.0", "language_code": language, "format": "transcribe",
                         "topic": STT_TOPIC, "keyterms": json.dumps(keyterms, ensure_ascii=False)})
        attempts.append({"model": "prisma-v3.0", "language_code": language, "format": "transcribe"})
    # Prisma v2.5 (the default model) as the last fallback
    attempts.append({"language_code": single_language, "format": "transcribe"})

    last = None
    for data in attempts:
        resp = requests.post(url, headers=headers, data=data, timeout=60,
                             files={"audio_file": (filename, audio, "audio/wav")})
        if resp.status_code == 200:
            body = resp.json()
            return {
                "transcript": (body.get("transcript") or "").strip(),
                "language": body.get("detected_language_code") or single_language,
                "model": body.get("model") or data.get("model") or "prisma-v2.5",
            }
        last = resp
        etype, _ = _error_info(resp)
        if not (resp.status_code == 422 or (resp.status_code == 400 and etype in _RETRY_TYPES)):
            break
    _raise(last, "speech-to-text")


# Small memory cache so the same sentence is not paid for twice.
_tts_cache: "OrderedDict[tuple[str, str], tuple[bytes, str]]" = OrderedDict()


def speak(text: str, lang: str = "hi") -> tuple[bytes, str]:
    """Turn text into speech with Gnani Timbre. Returns (audio_bytes, mime_type).

    lang is a short code: hi, en, mr, gu, bn, ta, te or kn.
    """
    if not settings.gnani_ready:
        raise GnaniError("Gnani API key not found. Put GNANI_API_KEY in the .env file and restart.")
    key = (text, lang)
    if key in _tts_cache:
        _tts_cache.move_to_end(key)
        return _tts_cache[key]

    lang = lang if lang in settings.voices else "hi"
    body = {
        "text": text,
        "model": settings.tts_model,
        "voice": settings.voices[lang],
        "language": f"{lang}-IN",
        "speed": 1.0,
        "audio_config": {"sample_rate": 24000, "num_channels": 1, "sample_width": 2,
                         "encoding": "linear_pcm", "container": "mp3", "bitrate": "64k"},
    }
    url = f"{settings.gnani_base}/api/v1/tts/inference"
    headers = {"X-API-Key-ID": settings.gnani_key, "Content-Type": "application/json"}

    resp = requests.post(url, headers=headers, json=body, timeout=60)
    mime = "audio/mpeg"
    if resp.status_code in (400, 422):  # if MP3 is not accepted, ask for plain WAV
        body["audio_config"] = {"sample_rate": 24000, "num_channels": 1, "sample_width": 2,
                                "encoding": "linear_pcm", "container": "wav"}
        resp = requests.post(url, headers=headers, json=body, timeout=60)
        mime = "audio/wav"
    if resp.status_code != 200:
        _raise(resp, "text-to-speech")

    _tts_cache[key] = (resp.content, mime)
    if len(_tts_cache) > 300:
        _tts_cache.popitem(last=False)
    return resp.content, mime
