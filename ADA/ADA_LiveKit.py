import asyncio
import os
import logging
import json
from dotenv import load_dotenv

# LiveKit Imports
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    cli,
    llm,
    Agent,
    AgentSession,
    function_tool,
    RunContext
)
from livekit.plugins import deepgram, openai, silero, elevenlabs, google
from livekit import rtc

try:
    from WIDGETS import to_do_list, calendar_widget, email_client, system
except ImportError:
    # Fallback if running from root directory context or if path needs adjustment
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from WIDGETS import to_do_list, calendar_widget, email_client, system

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lisa-voice-agent")

# --- Configuration ---
STT_PROVIDER = "deepgram"  # or "openai", "google"
TTS_PROVIDER = "deepgram"  # or "elevenlabs", "openai", "google"
LLM_PROVIDER = "gemini"    # or "anthropic", "openai"

async def entrypoint(ctx: JobContext):
    """
    The main entrypoint for the Voice Agent (L.I.S.A.).
    """
    
    # 1. Connect to the room
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    participant = await ctx.wait_for_participant()
    logger.info(f"Participant connected: {participant.identity}")

    # 2. Initialize Components
    
    # STT
    if STT_PROVIDER == "deepgram":
        stt_plugin = deepgram.STT()
    elif STT_PROVIDER == "google":
        stt_plugin = google.STT()
    else:
        stt_plugin = openai.STT()

    # LLM
    if LLM_PROVIDER == "gemini":
        # Use Gemini 2.0 Flash (or newer if available)
        llm_plugin = google.LLM(model="gemini-2.0-flash-exp")
    else:
        llm_plugin = openai.LLM(model="gpt-4o")

    # TTS
    if TTS_PROVIDER == "deepgram":
        tts_plugin = deepgram.TTS()
    elif TTS_PROVIDER == "elevenlabs":
        tts_plugin = elevenlabs.TTS()
    elif TTS_PROVIDER == "google":
        tts_plugin = google.TTS()
    else:
        tts_plugin = openai.TTS()
        
    # VAD
    vad_plugin = silero.VAD.load()

    # 3. Define Tools
    
    @function_tool
    async def get_system_info(ctx: RunContext):
        """Get the current system information"""
        return system.info()

    @function_tool
    async def set_timer(ctx: RunContext, seconds: int):
        """Set a timer"""
        async def _timer():
            await asyncio.sleep(seconds)
            # Timer completion notification would go here
            logger.info(f"Timer for {seconds} seconds finished.")
        
        asyncio.create_task(_timer())
        return f"Timer set for {seconds} seconds."

    @function_tool
    async def add_todo_task(ctx: RunContext, task: str):
        """Add a task to the todo list"""
        return to_do_list.add_task(task)

    @function_tool
    async def delete_todo_task(ctx: RunContext, task: str):
        """Delete a task from the todo list"""
        return to_do_list.delete_task(task)

    @function_tool
    async def list_todo_tasks(ctx: RunContext):
        """List all todo tasks"""
        return to_do_list.display_todo_list()

    # 4. Create the Agent
    agent = Agent(
        instructions="You are L.I.S.A. (Life Integrated System Architecture), an advanced AI command center assistant. You are professional, efficient, and slightly sci-fi in tone. Keep responses concise and authoritative.",
        tools=[get_system_info, set_timer, add_todo_task, delete_todo_task, list_todo_tasks],
    )

    # 5. Create the Session
    session = AgentSession(
        vad=vad_plugin,
        stt=stt_plugin,
        llm=llm_plugin,
        tts=tts_plugin,
    )

    # 6. Start the Session
    # This attaches the agent to the room and starts the pipeline
    await session.start(agent=agent, room=ctx.room)

    # 7. Initial Greeting
    await session.generate_reply(instructions="Greet the Commander (user) as L.I.S.A. and confirm systems are online.")

    # 8. Start Background Tasks
    async def broadcast_stats():
        while True:
            try:
                stats = system.get_stats_dict()
                payload = json.dumps(stats)
                
                # Send data packet to room
                await ctx.room.local_participant.publish_data(
                    payload.encode("utf-8"),
                    reliable=True,
                    topic="system_stats"
                )
            except Exception as e:
                logger.error(f"Error broadcasting stats: {e}")
            
            await asyncio.sleep(2) # Broadcast every 2 seconds

    asyncio.create_task(broadcast_stats())

    # 9. Listen for Data Packets (Chat Injection and Hand Gestures)
    @ctx.room.on("data_received")
    def on_data_received(data_packet: rtc.DataPacket):
        payload = data_packet.data.decode("utf-8")
        
        if data_packet.topic == "chat_message":
            logger.info(f"Received chat injection: {payload}")
            
            # Inject into the conversation context
            chat_msg = llm.ChatMessage(role="user", content=payload)
            session.chat_ctx.messages.append(chat_msg)
            
            # Trigger a response
            asyncio.create_task(session.generate_reply())
        
        elif data_packet.topic == "gesture":
            logger.info(f"Received gesture: {payload}")
            
            if payload == "Open_Palm":
                asyncio.create_task(session.generate_reply(instructions="User raised hand (Open Palm). Ask if they need assistance."))
            elif payload == "Closed_Fist":
                asyncio.create_task(session.generate_reply(instructions="User gestured Closed Fist. Acknowledge holding position."))
            elif payload == "Thumb_Up":
                 asyncio.create_task(session.generate_reply(instructions="User gestured Thumb Up. Acknowledge confirmation."))


if __name__ == "__main__":
    # Ensure standard keys are present
    if not os.getenv("DEEPGRAM_API_KEY"):
        logger.warning("DEEPGRAM_API_KEY not set. Deepgram features will fail.")
    
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
