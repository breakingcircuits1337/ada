import asyncio
import os
import logging
from dotenv import load_dotenv

# LiveKit Imports
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    cli,
    llm,
)
from livekit.agents.voice_assistant import VoiceAssistant
from livekit.plugins import deepgram, openai, silero, elevenlabs
from livekit import rtc

try:
    from .WIDGETS import to_do_list, calendar_widget, email_client
except ImportError:
    # Fallback if running from root directory context
    from ADA.WIDGETS import to_do_list, calendar_widget, email_client

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ada-voice-agent")

# --- Configuration ---
# You can switch models here
STT_PROVIDER = "deepgram"  # or "openai"
TTS_PROVIDER = "deepgram"  # or "elevenlabs", "openai"
LLM_PROVIDER = "openai"    # or "anthropic" (if plugin installed)

async def entrypoint(ctx: JobContext):
    """
    The main entrypoint for the Voice Agent.
    This function is called when a user connects to the room.
    """
    
    # 1. Connect to the room
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    participant = await ctx.wait_for_participant()
    logger.info(f"Participant connected: {participant.identity}")

    # 2. Initialize Components
    
    # STT (Speech to Text)
    if STT_PROVIDER == "deepgram":
        stt = deepgram.STT()
    else:
        stt = openai.STT()

    # LLM (Language Model)
    # Using GPT-4o for best reasoning
    llm_plugin = openai.LLM(model="gpt-4o")

    # TTS (Text to Speech)
    if TTS_PROVIDER == "deepgram":
        tts = deepgram.TTS()
    elif TTS_PROVIDER == "elevenlabs":
        tts = elevenlabs.TTS()
    else:
        tts = openai.TTS()
        
    # VAD (Voice Activity Detection)
    vad = silero.VAD.load()

    # 3. Create the Voice Assistant
    agent = VoiceAssistant(
        vad=vad,
        stt=stt,
        llm=llm_plugin,
        tts=tts,
        fnc_ctx=None, # We will add tools below
    )

    # 4. Define Tools (Equivalent to ADA_Local functions)
    
    @agent.llm.ai_callable(description="Get the current system information")
    async def get_system_info():
        # In a real scenario, this might query the actual server or a remote agent
        return "System Status: Online. Running on Secure Server. All systems nominal."

    @agent.llm.ai_callable(description="Set a timer")
    async def set_timer(seconds: int):
        # Note: This sets a timer on the server side/agent side. 
        # To notify the user, the agent will speak when it's done.
        async def _timer():
            await asyncio.sleep(seconds)
            # Interrupt current speech to announce timer
            await agent.say(f"Timer for {seconds} seconds is up!", allow_interruptions=True)
        
        asyncio.create_task(_timer())
        return f"Timer set for {seconds} seconds."

    @agent.llm.ai_callable(description="Add a task to the todo list")
    async def add_todo_task(task: str):
        return to_do_list.add_task(task)

    @agent.llm.ai_callable(description="Delete a task from the todo list")
    async def delete_todo_task(task: str):
        return to_do_list.delete_task(task)

    @agent.llm.ai_callable(description="List all todo tasks")
    async def list_todo_tasks():
        return to_do_list.display_todo_list()

    # 5. Start the Assistant
    agent.start(ctx.room, participant)

    # 6. Initial Greeting
    await agent.say("Hello Sir. ADA is connected via LiveKit. How can I help you today?", allow_interruptions=True)

    # 7. Listen for Data Packets (Chat Injection from REST API)
    @ctx.room.on("data_received")
    def on_data_received(data_packet: rtc.DataPacket):
        if data_packet.topic == "chat_message":
            message_text = data_packet.data.decode("utf-8")
            logger.info(f"Received chat injection: {message_text}")
            
            # Inject into the conversation context
            chat_ctx = agent.chat_ctx
            chat_ctx.append(role="user", text=message_text)
            
            # Trigger a response
            asyncio.create_task(agent.say(f"I received a message: {message_text}", allow_interruptions=True))

if __name__ == "__main__":
    # Ensure standard keys are present
    if not os.getenv("DEEPGRAM_API_KEY"):
        logger.warning("DEEPGRAM_API_KEY not set. Deepgram features will fail.")
    
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
