import dotenv

dotenv.load_dotenv()

import base64
import json
import os
from uuid import UUID
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import src.agent.service as service
import src.agent.models as models

app = FastAPI()

origins = os.getenv("CORS_ORIGINS", "").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _parse_message(msg: dict) -> models.MessageType:
    if "parts" in msg:
        return models.RunAgentUserMessage(
            parts=[
                models.UserMessagePart(
                    text=part.get("text"),
                    data=base64.b64decode(part["data"]) if part.get("data") else None,
                    mime_type=part.get("mime_type"),
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


@app.post("/chat")
async def chat_endpoint(request: Request):
    body = await request.json()
    inp = models.RunAgentInput(
        conversation_id=body["conversation_id"],
        message=_parse_message(body["message"]),
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


@app.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(conversation_id: UUID):
    steps = service.get_conversation_history(conversation_id)
    return [step.model_dump() for step in steps]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
