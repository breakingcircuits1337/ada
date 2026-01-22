import asyncio
import os
import logging
import json
import sys
from typing import Optional

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
    RunContext,
    vad as agent_vad  # Import vad module to access BaseVAD and VADCapabilities
)
from livekit.plugins import deepgram, openai, silero, elevenlabs, google
from livekit import rtc

# Local Imports
# Handle import paths for different execution contexts (root vs subdirectory)
try:
    from WIDGETS import to_do_list, calendar_widget, email_client, system
except ImportError:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from WIDGETS import to_do_list, calendar_widget, email_client, system

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("lisa-voice-agent")

# --- Configuration ---
# Providers: "deepgram", "openai", "google", "elevenlabs"
STT_PROVIDER = os.getenv("STT_PROVIDER", "deepgram")
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "deepgram")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")

class FixedSileroVAD(silero.VAD):
    """
    Wrapper around silero.VAD to fix missing super().__init__() call
    in livekit-plugins-silero v0.2.0.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Manually initialize the base VAD class (which initializes EventEmitter)
        # because silero.VAD.__init__ fails to call super().__init__()
        # Silero VAD processes in 40ms chunks
        caps = agent_vad.VADCapabilities(update_interval=0.04)
        agent_vad.VAD.__init__(self, capabilities=caps)

async def entrypoint(ctx: JobContext):
    """
    The main entrypoint for the L.I.S.A. Voice Agent.
    
    Initializes the connection, configures AI plugins (STT, LLM, TTS),
    defines tool capabilities, and manages the agent session.
    """
    
    # 1. Connect to the room
    logger.info(f"Connecting to room: {ctx.room.name if ctx.room else 'Unknown'}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    participant = await ctx.wait_for_participant()
    logger.info(f"Participant connected: {participant.identity}")

    # 2. Initialize AI Components
    stt_plugin = _get_stt_plugin()
    llm_plugin = _get_llm_plugin()
    tts_plugin = _get_tts_plugin()
    # Use FixedSileroVAD to avoid AttributeError: 'VAD' object has no attribute '_events'
    vad_plugin = FixedSileroVAD()

    # 3. Define Tools
    
    @function_tool
    async def get_system_info(ctx: RunContext) -> str:
        """Get the current system information (CPU, RAM, GPU)."""
        return system.info()

    @function_tool
    async def set_timer(ctx: RunContext, seconds: int) -> str:
        """Set a timer for a specific number of seconds."""
        async def _timer():
            await asyncio.sleep(seconds)
            # Future: Send a notification or voice alert
            logger.info(f"Timer for {seconds} seconds finished.")
        
        asyncio.create_task(_timer())
        return f"Timer set for {seconds} seconds."

    @function_tool
    async def add_todo_task(ctx: RunContext, task: str) -> str:
        """Add a task to the todo list."""
        return to_do_list.add_task(task)

    @function_tool
    async def delete_todo_task(ctx: RunContext, task: str) -> str:
        """Delete a task from the todo list."""
        return to_do_list.delete_task(task)

    @function_tool
    async def list_todo_tasks(ctx: RunContext) -> str:
        """List all current todo tasks."""
        return to_do_list.display_todo_list()

    # 4. Create the Agent
    agent = Agent(
        instructions=(
            "You are L.I.S.A. (Life Integrated System Architecture), an advanced AI command center assistant. "
            "You are professional, efficient, and slightly sci-fi in tone. "
            "Keep responses concise and authoritative. "
            "You have access to system stats, a todo list, and timer functions."
        ),
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
    await session.start(agent=agent, room=ctx.room)

    # 7. Initial Greeting
    await session.generate_reply(instructions="Greet the Commander (user) as L.I.S.A. and confirm systems are online.")

    # 8. Start Background Tasks
    stats_task = asyncio.create_task(_broadcast_stats(ctx))

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
            _handle_gesture(payload, session)

def _get_stt_plugin():
    if STT_PROVIDER == "deepgram":
        return deepgram.STT()
    elif STT_PROVIDER == "google":
        return google.STT()
    return openai.STT()

def _get_llm_plugin():
    if LLM_PROVIDER == "gemini":
        # User requested Gemini 3.0. Use env var GEMINI_MODEL to configure specific version.
        # Defaulting to a high-performance model available in the plugin.
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")
        return google.LLM(model=model_name)
    return openai.LLM(model="gpt-4o")

def _get_tts_plugin():
    if TTS_PROVIDER == "deepgram":
        return deepgram.TTS()
    elif TTS_PROVIDER == "elevenlabs":
        return elevenlabs.TTS()
    elif TTS_PROVIDER == "google":
        return google.TTS()
    return openai.TTS()

async def _broadcast_stats(ctx: JobContext):
    """
    Periodically broadcasts system statistics to the room via data packets.
    """
    while True:
        try:
            stats = system.get_stats_dict()
            payload = json.dumps(stats)
            
            # Send data packet to room
            if ctx.room and ctx.room.local_participant:
                await ctx.room.local_participant.publish_data(
                    payload.encode("utf-8"),
                    reliable=True,
                    topic="system_stats"
                )
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error broadcasting stats: {e}")
        
        await asyncio.sleep(2)

def _handle_gesture(gesture: str, session: AgentSession):
    """
    Reacts to specific hand gestures with voice responses.
    """
    instruction = ""
    if gesture == "Open_Palm":
        instruction = "User raised hand (Open Palm). Ask if they need assistance."
    elif gesture == "Closed_Fist":
        instruction = "User gestured Closed Fist. Acknowledge holding position."
    elif gesture == "Thumb_Up":
        instruction = "User gestured Thumb Up. Acknowledge confirmation."
    
    if instruction:
        asyncio.create_task(session.generate_reply(instructions=instruction))

if __name__ == "__main__":
    # Ensure standard keys are present
    if not os.getenv("DEEPGRAM_API_KEY"):
        logger.warning("DEEPGRAM_API_KEY not set. Deepgram features will fail.")
    
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
