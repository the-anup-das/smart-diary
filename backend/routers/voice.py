"""
Voice / Speech-to-Text router.

Architecture
------------
This router is a thin proxy between the diary frontend and any
OpenAI-compatible STT server (we ship faster-whisper-server in compose).

Three endpoints:
  GET  /api/voice/status     — is STT configured? is the model loaded?
  POST /api/voice/warm       — pre-load the model (called silently on page load)
  POST /api/voice/transcribe — transcribe one audio chunk (called every ~5 s)

The entire voice feature is **disabled** when STT_BASE_URL is not set in the
environment.  No UI is shown, no errors are raised.

Model memory strategy (handled by faster-whisper-server)
---------------------------------------------------------
  • Model loads on the first transcription request (lazy, automatic).
  • /api/voice/warm triggers this load in the background when the page opens,
    so the model is ready by the time the user clicks the mic.
  • After WHISPER__MODEL_LOAD_TTL seconds of inactivity (default: 1800 = 30 min)
    the STT server auto-unloads the model from RAM.
  • The frontend shows a "Loading Whisper…" state if /api/voice/status reports
    the model is not yet loaded, polling until it is.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from .auth import verify_session
import openai
import httpx
import os
import io
import tempfile

router = APIRouter()

# ── configuration ─────────────────────────────────────────────────────────────

STT_BASE_URL: str | None = os.getenv("STT_BASE_URL", "").strip() or None
STT_API_KEY: str = os.getenv("STT_API_KEY", "not-needed")
STT_MODEL: str = os.getenv("STT_MODEL", "Systran/faster-whisper-base.en")

# ── lazy singleton client ──────────────────────────────────────────────────────

_stt_client: openai.OpenAI | None = None


def _client() -> openai.OpenAI:
    """Return the shared STT client, creating it on first call."""
    global _stt_client
    if _stt_client is None:
        if not STT_BASE_URL:
            raise HTTPException(
                status_code=503,
                detail="STT service is not configured (STT_BASE_URL not set).",
            )
        _stt_client = openai.OpenAI(base_url=STT_BASE_URL, api_key=STT_API_KEY)
    return _stt_client


# ── helpers ────────────────────────────────────────────────────────────────────

async def _is_model_loaded() -> bool:
    """
    Ask the faster-whisper-server if our model is currently loaded in memory.

    The server exposes GET /v1/models which lists currently-loaded models.
    Returns False if unreachable or model not found.
    """
    if not STT_BASE_URL:
        return False
    try:
        # Strip trailing /v1 so we can probe the models list
        base = STT_BASE_URL.rstrip("/")
        async with httpx.AsyncClient(timeout=3.0) as http:
            res = await http.get(f"{base}/models")
        if res.status_code != 200:
            return False
        data = res.json()
        model_ids = [m.get("id", "") for m in data.get("data", [])]
        return any(STT_MODEL in mid for mid in model_ids)
    except Exception:
        return False


# ── endpoints ──────────────────────────────────────────────────────────────────

@router.get("/api/voice/status")
async def voice_status(user_id: str = Depends(verify_session)):
    """
    Called by the frontend on page load to decide whether to show the mic button.

    Returns:
        enabled      – True if STT_BASE_URL is set
        model_loaded – True if the Whisper model is already in RAM
    """
    enabled = bool(STT_BASE_URL)
    loaded = await _is_model_loaded() if enabled else False
    return {"enabled": enabled, "model_loaded": loaded}


@router.post("/api/voice/warm")
async def voice_warm(user_id: str = Depends(verify_session)):
    """
    Pre-warm the Whisper model by sending a 1-second silent WAV.

    Called in the background when the diary page opens so the model is
    already loaded by the time the user clicks the mic.
    Idempotent — safe to call multiple times.
    """
    if not STT_BASE_URL:
        return {"ok": False, "reason": "STT not configured"}

    # Minimal valid WAV: 44-byte header + 1 s of silence at 16 kHz mono 16-bit
    sample_rate = 16000
    num_samples = sample_rate  # 1 second
    data_size = num_samples * 2  # 16-bit = 2 bytes/sample
    wav = bytearray()
    # RIFF header
    wav += b"RIFF"
    wav += (36 + data_size).to_bytes(4, "little")
    wav += b"WAVE"
    # fmt chunk
    wav += b"fmt "
    wav += (16).to_bytes(4, "little")         # chunk size
    wav += (1).to_bytes(2, "little")          # PCM
    wav += (1).to_bytes(2, "little")          # channels
    wav += sample_rate.to_bytes(4, "little")  # sample rate
    wav += (sample_rate * 2).to_bytes(4, "little")  # byte rate
    wav += (2).to_bytes(2, "little")          # block align
    wav += (16).to_bytes(2, "little")         # bits per sample
    # data chunk
    wav += b"data"
    wav += data_size.to_bytes(4, "little")
    wav += b"\x00" * data_size  # silence

    try:
        client = _client()
        client.audio.transcriptions.create(
            model=STT_MODEL,
            file=("silence.wav", io.BytesIO(bytes(wav)), "audio/wav"),
            language="en",
        )
        return {"ok": True}
    except Exception as e:
        # Warm failures are non-fatal — model will load on first real request
        return {"ok": False, "reason": str(e)}


@router.post("/api/voice/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    user_id: str = Depends(verify_session),
):
    """
    Transcribe one audio chunk (~5 s) and return its text.

    Called repeatedly while the user is speaking.  Each chunk is a
    complete, standalone audio file produced by the MediaRecorder
    stop-restart loop in the frontend.
    """
    if not STT_BASE_URL:
        raise HTTPException(
            status_code=503,
            detail="STT service is not configured. Set STT_BASE_URL to enable voice input.",
        )

    content = await audio.read()

    # Skip silent / near-empty blobs the browser sometimes emits
    if len(content) < 1024:
        return {"text": ""}

    content_type = (audio.content_type or "audio/webm").split(";")[0].strip()
    ext_map = {
        "audio/webm": ".webm",
        "audio/ogg": ".ogg",
        "audio/mp4": ".mp4",
        "audio/wav": ".wav",
        "audio/mpeg": ".mp3",
    }
    suffix = ext_map.get(content_type, ".webm")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        with open(tmp_path, "rb") as f:
            result = _client().audio.transcriptions.create(
                model=STT_MODEL,
                file=f,
                language="en",
            )
        return {"text": result.text or ""}
    except openai.APIConnectionError:
        raise HTTPException(
            status_code=503,
            detail=(
                "Cannot reach the STT server. "
                "Ensure the stt-server container is running and STT_BASE_URL is correct."
            ),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription error: {str(e)}")
    finally:
        os.unlink(tmp_path)
