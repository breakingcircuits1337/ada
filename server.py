import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from livekit import api
from dotenv import load_dotenv
import uvicorn
from pydantic import BaseModel

# Load environment variables
load_dotenv()

LIVEKIT_URL = os.getenv("LIVEKIT_URL")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")

if not all([LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET]):
    print("Warning: LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET must be set in your .env file")

app = FastAPI(title="L.I.S.A Command Center API")

# Mount static files (Frontend)
from fastapi.staticfiles import StaticFiles
import os

# Create frontend directory if it doesn't exist
if not os.path.exists("frontend"):
    os.makedirs("frontend")

app.mount("/command-center", StaticFiles(directory="frontend", html=True), name="frontend")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TokenRequest(BaseModel):
    room_name: str
    participant_name: str

class ChatMessage(BaseModel):
    room_name: str
    message: str
    identity: str = "API_User"

@app.post("/token")
async def create_token(request: TokenRequest):
    """
    Generate a LiveKit access token for a client.
    """
    try:
        grant = api.VideoGrant(
            room_join=True,
            room=request.room_name,
            can_publish=True,
            can_subscribe=True,
        )
        
        token = api.AccessToken(
            LIVEKIT_API_KEY,
            LIVEKIT_API_SECRET,
            grant=grant,
            identity=request.participant_name,
            name=request.participant_name,
        )
        
        return {"token": token.to_jwt()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
async def send_chat_message(chat: ChatMessage):
    """
    Inject a chat message into a room programmatically.
    """
    try:
        lkapi = api.LiveKitAPI(LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        
        # Publish data to the room (Agents can listen for this)
        await lkapi.room.send_data(
            room=chat.room_name,
            data=chat.message.encode("utf-8"),
            kind=api.DataPacketKind.RELIABLE,
            topic="chat_message"
        )
        
        # Also try to send as a standard chat message if supported by clients
        # Note: LiveKit server APIs for direct chat injection might vary, 
        # usually data packets are preferred for custom signaling.
        
        await lkapi.aclose()
        return {"status": "sent", "message": chat.message}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
