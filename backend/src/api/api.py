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
import src.api.media as media
import src.pipeline.service as pipeline
from src.pipeline.models import DraftError, PipelineInput
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
        via="sandbox",
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


@app.post("/drafts/{draft_id}/dishes/{dish_id}/revise")
async def revise_draft_dish_endpoint(
    draft_id: UUID,
    dish_id: str,
    request: Request,
    user_id: str = Depends(_get_user_id_from_jwt),
):
    """Applies a correction in the user's words to one draft dish."""
    body = await request.json()
    try:
        return await pipeline.revise_draft_dish(
            user_id, draft_id, dish_id, body.get("instruction", "")
        )
    except DraftError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/drafts/{draft_id}/dishes/{dish_id}")
async def delete_draft_dish_endpoint(
    draft_id: UUID,
    dish_id: str,
    user_id: str = Depends(_get_user_id_from_jwt),
):
    """Removes one draft dish; returns the draft, or null once it's empty."""
    try:
        return {
            "draft": await asyncio.to_thread(
                pipeline.delete_draft_dish, user_id, draft_id, dish_id
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


if __name__ == "__main__":
    import uvicorn

    debug = os.getenv("DEBUG", "false").lower() == "true"
    uvicorn.run(
        "src.api.api:app" if debug else app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
        reload=debug,
    )
