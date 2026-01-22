import ollama
import asyncio
import pyaudio
from RealtimeSTT import AudioToTextRecorder
from RealtimeTTS import TextToAudioStream, SystemEngine, CoquiEngine
import torch  # Import the torch library
import re
import time
import os
from .WIDGETS import system, timer, project, camera, to_do_list, calendar_widget, email_client

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = 'pFZP5JQG7iQjIQuC4Bku'

FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

class ADA:
    def __init__(self):
        print("initializing...")

        # Check for CUDA availability
        if torch.cuda.is_available():
            self.device = "cuda"
            print("CUDA is available. Using GPU.")
        else:
            self.device = "cpu"
            print("CUDA is not available. Using CPU.")

        self.model = "gemma3:4b-it-q4_K_M" #This is the smallest version of gemma3 for consistent function calling use gemma3:4b-it-q4_K_M  or higher if your computer is not strong enough use ada_online
        self.system_behavior = """
            Your name is ADA (Advanced Design Assistant) you are a helpful AI assistant.  You are an expert in All STEM Fields providing concise and accurate information. When asked to perform a task, respond with the code to perform that task wrapped in ```tool_code```.  If the task does not require a function call, provide a direct answer without using ```tool_code```.  Always respond in a helpful and informative manner."

            You speak with a british accent and address people as Sir.
        """

        self.instruction_prompt_with_function_calling = '''
            At each turn, if you decide to invoke any of the function(s), it should be wrapped with ```tool_code```. If you decide to call a function the response should only have the function wrapped in tool code nothing more. The python methods described below are imported and available, you can only use defined methods also only call methods when you are sure they need to be called. The generated code should be readable and efficient. 
            
            The response to a method will be wrapped in ```tool_output``` use the response to give the user an answer based on the information provided that is wrapped in ```tool_ouput```.

            For regular prompts do not call any functions or wrap the response in ```tool_code```.

            The following Python methods are available:

            ```python
            def camera.open() -> None:
                """Open the camera"""

            def system.info() -> None:
                """ Gathers and prints system information including CPU, RAM, and GPU details. Only call when user ask about computer information. """

            def timer.set(time_str):
                """
                Counts down from a specified time in HH:MM:SS format.

                Args:
                    time_str (str): The time to count down from in HH:MM:SS format.
                """
            def project.create_folder(folder_name):
                """
                Creates a project folder and a text file to store chat history.

                Args:
                    folder_name (str): The name of the project folder to create.
                """

            def todo.list():
                """ Displays the current todo list """

            def calendar.add(title, date_str, time_str, description=""):
                """ 
                Adds an event to the calendar. 
                Args: 
                    title (str): Event title
                    date_str (str): YYYY-MM-DD
                    time_str (str): HH:MM
                    description (str): Optional details
                """
            
            def calendar.list(date_str=None):
                """ Lists events. Optional date_str (YYYY-MM-DD) to filter. """
            
            def calendar.delete(title):
                """ Deletes an event by title. """

            def email.send(to_email, subject, body):
                """ Sends an email. """
            
            def email.read(limit=5):
                """ Reads latest N emails. """
        ```

        User: {user_message}
        '''

        self.available_tools = {
            "camera.open": camera.open,
            "system.info": system.info,
            "timer.set": timer.set,
            "project.create_folder": project.create_folder,
            "todo.add": to_do_list.add_task,
            "todo.delete": to_do_list.delete_task,
            "todo.list": to_do_list.display_todo_list,
            "calendar.add": calendar_widget.add_event,
            "calendar.list": calendar_widget.list_events,
            "calendar.delete": calendar_widget.delete_event,
            "email.send": email_client.send_email,
            "email.read": email_client.read_emails
        }

        self.model_params = {
            'temperature': 0.1,
            'top_p': 0.9,
        }
        self.conversation_history = []

        self.input_queue = asyncio.Queue()
        self.response_queue = asyncio.Queue()
        self.audio_queue = asyncio.Queue()
        self.recorder_config = {
            'model': 'large-v3',
            'spinner': False,
            'language': 'en',
            'silero_sensitivity': 0.01,
            'webrtc_sensitivity': 3,
            'post_speech_silence_duration': 0.1,
            'min_length_of_recording': 0.2,
            'min_gap_between_recordings': 0,

            #'realtime_model_type': 'tiny.en',
            #'enable_realtime_transcription': True,
            #'on_realtime_transcription_update': self.clear_queues,
        }

        try:
            self.recorder = AudioToTextRecorder(**self.recorder_config)
        except Exception as e:
            print(f"Error initializing AudioToTextRecorder: {e}")
            self.recorder = None  # Or handle this appropriately

        try:
            self.pya = pyaudio.PyAudio()
        except Exception as e:
            print(f"Error initializing PyAudio: {e}")
            self.pya = None
        
        self.response_start_time = None
        self.audio_start_time = None
        #self.engine = CoquiEngine()
        self.engine = SystemEngine()
        self.stream = TextToAudioStream(self.engine)
        self.first_audio_byte_time = None
        self.speech_to_text_time = None

    async def clear_queues(self, text=""):
        """Clears all data from the input, response, and audio queues."""
        queues = [self.input_queue, self.response_queue, self.audio_queue]
        for q in queues:
            while not q.empty():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    break  # Queue is empty

    async def input_message(self):
        while True:
            try:
                prompt = await asyncio.to_thread(input, "Enter your message: ")
                if prompt.lower() == "exit":
                    await self.input_queue.put(None)  # Signal to exit
                    break
                await self.clear_queues()
                self.prompt_start_time = time.time()
                await self.input_queue.put(prompt)
            except Exception as e:
                print(f"Error in input_message: {e}")
                continue  # Continue the loop even if there's an error

    async def send_prompt(self):
        while True:
            try:
                prompt = await self.input_queue.get()
                if prompt is None:
                    break  # Exit loop if None is received
                
                self.response_start_time = time.time() #start timer when prompt is sent
                
                messages = [{"role": "system", "content": self.system_behavior}] + self.conversation_history + [{"role": "user", "content": self.instruction_prompt_with_function_calling.format(user_message=prompt)}]
                try:
                    response = ollama.chat(model=self.model, messages=messages, stream=True)
                    full_response = ""
                    in_function_call = False
                    function_call = ""

                    for chunk in response:
                        chunk_content = chunk['message']['content']
                        if chunk_content == "```":
                            if in_function_call == True:
                                in_function_call = False
                                function_call += "```"
                                tool_output = self.extract_tool_call(function_call)

                                messages = [{"role": "system", "content": self.system_behavior}] + self.conversation_history + [{"role": "user", "content": self.instruction_prompt_with_function_calling.format(user_message=tool_output)}]
                                
                                response = ollama.chat(model=self.model, messages=messages, stream=True)
                                for chunk in response:
                                    chunk_content = chunk['message']['content']
                                    print(chunk_content, end="", flush=True)
                                    await self.response_queue.put(chunk_content)
                                print()
                                continue
                            else:
                               in_function_call = True

                        if in_function_call == False:
                            await self.response_queue.put(chunk_content)
                            await asyncio.sleep(0)
                        else:
                            function_call += chunk_content                        
                        if chunk_content:
                            print(chunk_content, end="", flush=True) #print chunks on same line
                            full_response += chunk_content
                    print() # new line
                    self.conversation_history.append({"role": "user", "content": prompt})
                    self.conversation_history.append({"role": "assistant", "content": full_response})

                except Exception as e:
                    print(f"An error occurred in send_prompt: {e}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Unexpected error in send_prompt: {e}")

            finally:  # Ensure the sentinel value is added even if an error occurs
                await self.response_queue.put(None)

    def extract_tool_call(self, text):
        import io
        from contextlib import redirect_stdout
        import shlex

        pattern = r"```tool_code\s*(.*?)\s*```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            code = match.group(1).strip()
            
            # Simple parsing of the function call
            # Expecting format: function.name(arg1, arg2="value")
            # This is a basic parser and might need robustness improvements for complex args
            try:
                # Extract function name
                func_name_match = re.match(r"^([\w\.]+)\(", code)
                if not func_name_match:
                     return "```tool_output\nError: Could not parse function name.\n```"
                
                func_name = func_name_match.group(1)
                
                if func_name not in self.available_tools:
                    return f"```tool_output\nError: Function '{func_name}' is not allowed or does not exist.\n```"
                
                # Extract arguments - this is a bit hacky for a full python parser, 
                # but safer than eval. For complex args, consider ast.literal_eval
                # or a proper parser. 
                # For now, let's assume the LLM generates valid python call syntax 
                # and we just want to run it IF it's in the whitelist.
                # BUT avoiding eval means we have to parse args.
                
                # Alternative: Use eval but with a restricted globals/locals dict
                # This is safer than raw eval but still has risks. 
                # Best practice is to NOT use eval at all.
                
                # Let's use ast.parse to safely extract args
                import ast
                tree = ast.parse(code)
                expr = tree.body[0]
                if not isinstance(expr, ast.Expr) or not isinstance(expr.value, ast.Call):
                     return "```tool_output\nError: Invalid function call syntax.\n```"
                
                call = expr.value
                # Verify function name again from AST to be sure
                call_func_name = ""
                if isinstance(call.func, ast.Attribute):
                    call_func_name = f"{call.func.value.id}.{call.func.attr}"
                elif isinstance(call.func, ast.Name):
                    call_func_name = call.func.id
                
                if call_func_name != func_name:
                     return "```tool_output\nError: Function name mismatch.\n```"

                # Prepare arguments
                args = []
                for arg in call.args:
                    if isinstance(arg, ast.Constant):
                        args.append(arg.value)
                    else:
                        # Fallback for complex types if needed, or error
                        # For this MVP, we might just try to eval the arg strictly if it's a literal
                        try:
                            args.append(ast.literal_eval(arg))
                        except:
                             return "```tool_output\nError: Only literal arguments are supported.\n```"

                kwargs = {}
                for keyword in call.keywords:
                    if isinstance(keyword.value, ast.Constant):
                        kwargs[keyword.arg] = keyword.value.value
                    else:
                         try:
                            kwargs[keyword.arg] = ast.literal_eval(keyword.value)
                         except:
                             return "```tool_output\nError: Only literal keyword arguments are supported.\n```"

                # Execute
                f = io.StringIO()
                with redirect_stdout(f):
                    result = self.available_tools[func_name](*args, **kwargs)
                
                output = f.getvalue()
                r = result if output == '' else output
                return f'```tool_output\n{str(r).strip()}\n```'

            except Exception as e:
                return f"```tool_output\nError executing tool: {e}\n```"
        return None

    async def tts(self):
        while True:
            chunk = await self.response_queue.get()
            if chunk == None:
                continue
            if self.first_audio_byte_time is None:
                self.first_audio_byte_time = time.time()
                time_to_first_audio = self.first_audio_byte_time - self.prompt_start_time
                print(f"Time from prompt to first audio byte: {time_to_first_audio:.4f} seconds")
            self.stream.feed(chunk)
            self.stream.play_async()

    async def stt(self):
        if self.recorder is None:
            print("Audio recorder is not initialized.")
            return

        while True:
            try:
                text = await asyncio.to_thread(self.recorder.text)
                await self.clear_queues()
                await self.input_queue.put(text)
                print(text)
            except Exception as e:
                print(f"Error in listen: {e}")
                continue  # Continue the loop even if there's an error
