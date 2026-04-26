from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from .auth import verify_session
import openai
import os
import tempfile

router = APIRouter()

_stt_client: openai.OpenAI | None = None


def _get_stt_client() -> openai.OpenAI:
    """Lazy-initialise the STT client once from env vars."""
    global _stt_client
    if _stt_client is None:
        base_url = os.getenv("STT_BASE_URL")
        if not base_url:
            raise HTTPException(
                status_code=503,
                detail=(
                    "STT service is not configured. "
                    "Set STT_BASE_URL in your environment (e.g. http://host:port/v1)."
                ),
            )
        _stt_client = openai.OpenAI(
            base_url=base_url,
            api_key=os.getenv("STT_API_KEY", "not-needed"),
        )
    return _stt_client


@router.post("/api/voice/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    user_id: str = Depends(verify_session),
):
    """
    Receive an audio chunk from the browser and return its transcription.

    This endpoint is called repeatedly while the user is recording —
    each ~5-second chunk is sent here as soon as it's ready, and the
    returned text is appended live to the diary editor.

    The actual transcription is delegated to whatever OpenAI-compatible
    STT server is configured via STT_BASE_URL (e.g. LM Studio, a local
    Whisper server, or the real OpenAI API).
    """
    client = _get_stt_client()
    model = os.getenv("STT_MODEL", "whisper-1")

    # Determine file extension from the upload's content type
    content_type = audio.content_type or "audio/webm"
    ext_map = {
        "audio/webm": ".webm",
        "audio/ogg": ".ogg",
        "audio/mp4": ".mp4",
        "audio/wav": ".wav",
        "audio/mpeg": ".mp3",
    }
    suffix = ext_map.get(content_type.split(";")[0].strip(), ".webm")

    content = await audio.read()

    # Skip tiny/silent chunks (browser sometimes emits empty blobs)
    if len(content) < 1024:
        return {"text": ""}

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        with open(tmp_path, "rb") as f:
            result = client.audio.transcriptions.create(
                model=model,
                file=f,
                language="en",
            )
        return {"text": result.text or ""}
    except openai.APIConnectionError:
        raise HTTPException(
            status_code=503,
            detail="Cannot reach STT server. Check STT_BASE_URL and ensure your server is running.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription error: {str(e)}")
    finally:
        os.unlink(tmp_path)
