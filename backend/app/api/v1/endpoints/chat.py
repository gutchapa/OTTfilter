from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.chat_history import save_message, load_history

router = APIRouter()

class ChatRequest(BaseModel):
    session_id: str
    message: str

class ChatResponse(BaseModel):
    history: list[dict]
    reply: str

@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """A simple chat endpoint that echoes and persists messages."""
    try:
        # Load existing history
        history = load_history(req.session_id)
        # Generate reply (echo)
        reply = req.message
        # Save user message
        save_message(req.session_id, "user", req.message)
        # Save assistant reply
        save_message(req.session_id, "assistant", reply)
        # Reload full history
        history = load_history(req.session_id)
        return {"history": history, "reply": reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
