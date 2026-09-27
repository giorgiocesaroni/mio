import dotenv

dotenv.load_dotenv()

import asyncio
import base64
import json
import logging
import os
from uuid import UUID
from fastapi import Depends, FastAPI, File, Request, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import src.agent.service as service
import src.agent.models as models
import src.agent.providers as providers
import src.agent.repository as repository
import src.api.media as media
import src.pipeline.service as pipeline
from src.pipeline.models import DraftError, PipelineInput
from src.api.transcribe import transcribe_audio, MODEL_ID as TRANSCRIBE_MODEL_ID
from src.agent.utils import extract_tokens
import supabase

app = FastAPI()

logger = logging.getLogger(__name__)

origins = os.getenv("CORS_ORIGINS", "").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

supabase_client = supabase.create_client(
    os.getenv("SUPABASE_URL", ""),
    os.getenv("SUPABASE_KEY", ""),
)


def _get_user_id_from_jwt(request: Request) -> str:
    """Retrives the user from the JWT."""

    jwt = request.headers.get("Authorization")

    if jwt is None:
        raise HTTPException(status_code=403, detail="Missing JWT token")

    try:
        _, token = jwt.split(" ")
        response = supabase_client.auth.get_user(token)
        if response is None:
            raise HTTPException(
                status_code=403,
                detail="Invalid JWT token",
            )
        return response.user.id
    except Exception as e:
        raise HTTPException(
            status_code=403,
            detail="Invalid JWT token",
        )


def _parse_message(msg: dict) -> models.MessageType:
    if "parts" in msg:
        return models.RunAgentUserMessage(
            parts=[
                models.UserMessagePart(
                    text=part.get("text"),
                    data=base64.b64decode(part["data"]) if part.get("data") else None,
                    mime_type=part.get("mime_type"),
                    url=part.get("url"),
                )
                for part in msg["parts"]
            ],
        )
    match msg.get("type", "text"):
        case "text":
            return models.RunAgentUserMessage(
                parts=[models.UserMessagePart(text=msg["text"])],
            )
        case "image":
            return models.RunAgentUserMessage(
                parts=[
                    models.UserMessagePart(
                        data=base64.b64decode(msg["data"]),
                        mime_type=msg["mime_type"],
                    )
                ],
            )
        case "audio":
            return models.RunAgentUserMessage(
                parts=[
                    models.UserMessagePart(
                        data=base64.b64decode(msg["data"]),
                        mime_type=msg["mime_type"],
                    )
                ],
            )
        case _:
            raise ValueError(f"Unknown message type: {msg.get('type')}")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/models")
async def list_models():
    return {
        "models": sorted(providers.AVAILABLE_MODELS, key=lambda m: m["id"]),
        "default": providers.DEFAULT_MODEL_ID,
    }


@app.get("/usage")
async def usage_endpoint(
    user_id: str = Depends(_get_user_id_from_jwt),
):
    return service.get_usage_overview()


@app.post("/chat")
async def chat_endpoint(
    request: Request,
    user_id: str = Depends(
        _get_user_id_from_jwt,
    ),
):
    body = await request.json()
    inp = models.RunAgentInput(
        conversation_id=body["conversation_id"],
        user_id=user_id,
        message=_parse_message(body["message"]),
        thinking=body.get("thinking", True),
        model=body.get("model"),
        day=body.get("day"),
    )

    async def event_stream():
        try:
            async for step in service.run_agent(inp):
                yield f"data: {step.model_dump_json()}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'text': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/sandbox/log")
async def sandbox_log_endpoint(
    request: Request,
    user_id: str = Depends(_get_user_id_from_jwt),
):
    """Runs the logging pipeline and streams every stage, for debugging."""
    body = await request.json()
    message = await service.preprocess_message(
        _parse_message(body["message"]), user_id, None
    )
    inp = PipelineInput(
        user_id=user_id,
        message=message,
        day=body.get("day"),
        model=body.get("model"),
    )

    async def event_stream():
        async for step in pipeline.run(inp):
            yield f"data: {step.model_dump_json()}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/entries")
async def list_entries_endpoint(
    day: str,
    user_id: str = Depends(_get_user_id_from_jwt),
):
    """Pending log drafts and logs for a day, read together."""
    return await asyncio.to_thread(pipeline.list_day_entries, user_id, day)


@app.post("/drafts/{draft_id}/rows/{row_id}/revise")
async def revise_draft_row_endpoint(
    draft_id: UUID,
    row_id: str,
    request: Request,
    user_id: str = Depends(_get_user_id_from_jwt),
):
    """Applies a correction in the user's words to one draft entry."""
    body = await request.json()
    try:
        return await pipeline.revise_draft_row(
            user_id, draft_id, row_id, body.get("instruction", ""), body.get("model")
        )
    except DraftError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/drafts/{draft_id}/rows/{row_id}")
async def delete_draft_row_endpoint(
    draft_id: UUID,
    row_id: str,
    user_id: str = Depends(_get_user_id_from_jwt),
):
    """Removes one draft entry; returns the draft, or null once it's empty."""
    try:
        return {
            "draft": await asyncio.to_thread(
                pipeline.delete_draft_row, user_id, draft_id, row_id
            )
        }
    except DraftError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/drafts/{draft_id}/confirm")
async def confirm_draft_endpoint(
    draft_id: UUID,
    request: Request,
    user_id: str = Depends(_get_user_id_from_jwt),
):
    """Logs the given `row_ids` of the draft, or all of its rows when omitted."""
    body = await request.body()
    row_ids = (json.loads(body) if body else {}).get("row_ids")
    try:
        return await asyncio.to_thread(
            pipeline.confirm_draft, user_id, draft_id, row_ids
        )
    except DraftError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/drafts/{draft_id}/discard")
async def discard_draft_endpoint(
    draft_id: UUID,
    user_id: str = Depends(_get_user_id_from_jwt),
):
    try:
        await asyncio.to_thread(pipeline.discard_draft, user_id, draft_id)
    except DraftError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True}


@app.post("/logs/revise")
async def revise_logs_endpoint(
    request: Request,
    user_id: str = Depends(_get_user_id_from_jwt),
):
    """Applies a correction in the user's words to logged entries (one card)."""
    body = await request.json()
    try:
        return await pipeline.revise_logs(
            user_id,
            body["day"],
            body["log_ids"],
            body.get("instruction", ""),
            body.get("model"),
        )
    except DraftError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/logs/delete")
async def delete_logs_endpoint(
    request: Request,
    user_id: str = Depends(_get_user_id_from_jwt),
):
    body = await request.json()
    return await asyncio.to_thread(pipeline.delete_logs, user_id, body["log_ids"])


@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    user_id: str = Depends(_get_user_id_from_jwt),
):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 50MB)")
    try:
        url, mime_type = media.upload_media(
            user_id, data, file.content_type or "application/octet-stream"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")
    return {"url": url, "mime_type": mime_type}


@app.post("/transcribe")
async def transcribe_voice_memo(
    file: UploadFile = File(...),
    user_id: str = Depends(_get_user_id_from_jwt),
):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 25MB)")
    mime_type = file.content_type or "audio/wav"
    if not mime_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="Audio file required")
    logger.info(
        "POST /transcribe: user=%s filename=%s mime=%s bytes=%d",
        user_id,
        file.filename,
        mime_type,
        len(data),
    )
    try:
        result = await transcribe_audio(data, mime_type)
    except Exception as e:
        logger.exception("POST /transcribe failed")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}")
    logger.info(
        "POST /transcribe done: chars=%d cost=%s",
        len(result.text),
        result.cost,
    )
    uncached_input, cached_input, output = extract_tokens(result.usage)
    repository.insert_llm_invocation(
        total_cost=result.cost,
        raw_usage_metadata=result.usage,
        model_id=TRANSCRIBE_MODEL_ID,
        uncached_input_tokens=uncached_input,
        cached_input_tokens=cached_input,
        output_tokens=output,
        user_id=user_id,
        conversation_id=None,
    )
    return {"text": result.text}


@app.get("/conversations")
async def list_conversations(
    user_id: str = Depends(_get_user_id_from_jwt),
):
    conversations = service.get_conversations(user_id)
    return [c.model_dump() for c in conversations]


@app.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: UUID,
    user_id: str = Depends(
        _get_user_id_from_jwt,
    ),
):
    steps = service.get_conversation_history(conversation_id, user_id)
    return [step.model_dump() for step in steps]


if __name__ == "__main__":
    import uvicorn

    debug = os.getenv("DEBUG", "false").lower() == "true"
    uvicorn.run(
        "src.api.api:app" if debug else app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
        reload=debug,
    )
