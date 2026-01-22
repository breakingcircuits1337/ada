import os
import logging
import uvicorn
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
from livekit import api

# Load environment variables
load_dotenv()

# Configuration
LIVEKIT_URL = os.getenv("LIVEKIT_URL")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")

# Logging Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LISA-API")

if not all([LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET]):
    logger.warning("LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET must be set in your .env file")

app = FastAPI(title="L.I.S.A Command Center API")

# --- Static Files (Frontend) ---
if not os.path.exists("frontend"):
    os.makedirs("frontend")

app.mount("/command-center", StaticFiles(directory="frontend", html=True), name="frontend")

# --- Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Security: In production, restrict this to specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Models ---
class TokenRequest(BaseModel):
    room_name: str
    participant_name: str

class ChatMessage(BaseModel):
    room_name: str
    message: str
    identity: str = "API_User"

# --- Endpoints ---

@app.post("/token")
async def create_token(request: TokenRequest):
    """
    Generate a LiveKit access token for a client.
    
    Args:
        request (TokenRequest): Contains room_name and participant_name.
        
    Returns:
        dict: {"token": "jwt_string"}
    """
    try:
        grant = api.VideoGrants(
            room_join=True,
            room=request.room_name,
            can_publish=True,
            can_subscribe=True,
        )
        
        token = api.AccessToken(
            LIVEKIT_API_KEY,
            LIVEKIT_API_SECRET
        ).with_identity(
            request.participant_name
        ).with_name(
            request.participant_name
        ).with_grants(grant)
        
        return {"token": token.to_jwt()}
    except Exception as e:
        logger.error(f"Error creating token: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
async def send_chat_message(chat: ChatMessage):
    """
    Inject a chat message into a room programmatically via DataPacket.
    
    Args:
        chat (ChatMessage): Contains room_name and message content.
    """
    try:
        lkapi = api.LiveKitAPI(LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        
        # Publish data to the room (Agents can listen for this topic "chat_message")
        await lkapi.room.send_data(
            room=chat.room_name,
            data=chat.message.encode("utf-8"),
            kind=api.DataPacketKind.RELIABLE,
            topic="chat_message"
        )
        
        await lkapi.aclose()
        return {"status": "sent", "message": chat.message}
    except Exception as e:
        logger.error(f"Error sending chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint to verify API is running."""
    return {"status": "ok", "system": "L.I.S.A. Online"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
