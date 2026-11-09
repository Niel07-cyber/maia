"""Voice: turn a push-to-talk recording into text. The text then goes to the chat endpoint
like a typed message, so the technician sees (and can correct) what was understood."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel

from maia.agent.llm import ModelUnavailableError
from maia.api.deps import get_transcriber
from maia.api.limits import RateLimited
from maia.speech import Transcriber

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["voice"])

MAX_AUDIO_BYTES = 5 * 1024 * 1024  # about five minutes of compressed speech

TranscriberDep = Annotated[Transcriber, Depends(get_transcriber)]


class Transcript(BaseModel):
    text: str


@router.post("/transcribe", dependencies=[RateLimited])
async def transcribe(audio: UploadFile, transcriber: TranscriberDep) -> Transcript:
    content_type = (audio.content_type or "").split(";")[0]
    if not content_type.startswith("audio/"):
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"Expected an audio file, got '{content_type}'."
        )
    data = await audio.read(MAX_AUDIO_BYTES + 1)
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "The recording is too long.")
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The recording is empty.")
    try:
        text = transcriber.transcribe(data, audio.filename or "speech.webm")
    except ModelUnavailableError as exc:
        logger.warning("transcription failed: %s", exc)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Speech recognition is unavailable. Please type."
        ) from exc
    if not text:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "No speech was recognised. Please try again."
        )
    return Transcript(text=text)
