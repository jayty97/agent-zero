import threading, time, models, os, sys
import traceback
import logging
from ansio import application_keypad, mouse_input, raw_input
from ansio.input import InputEvent, get_input_event
from agent import Agent, AgentConfig
from python.helpers.print_style import PrintStyle
from python.helpers.files import read_file
from python.helpers import files
import python.helpers.timed_input as timed_input

input_lock = threading.Lock()
os.chdir(files.get_abs_path("./work_dir"))

# Set up logging
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'agent_zero.log')
logging.basicConfig(filename=log_file, level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add console logging
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

def initialize():
    """
    Initialize the agent with the necessary models and configuration.
    
    :return: Initialized Agent instance
    """
    try:
        logger.info("Initializing models...")
        
        chat_llm = models.get_openai_chat(model_name="gpt-4o-mini-2024-07-18", temperature=0)
        # chat_llm = models.get_ollama_chat(model_name="gemma2:latest", temperature=0)
        # chat_llm = models.get_lmstudio_chat(model_name="TheBloke/Mistral-7B-Instruct-v0.2-GGUF", temperature=0)
        # chat_llm = models.get_openrouter(model_name="meta-llama/llama-3-8b-instruct:free")
        # chat_llm = models.get_azure_openai_chat(deployment_name="gpt-4o-mini", temperature=0)
        # chat_llm = models.get_anthropic_chat(model_name="claude-3-5-sonnet-20240620", temperature=0)
        # chat_llm = models.get_google_chat(model_name="gemini-1.5-flash", temperature=0)
        # chat_llm = models.get_groq_chat(model_name="llama-3.1-70b-versatile", temperature=0)
        logger.info(f"Initialized chat model: {chat_llm}")

        utility_llm = models.get_openai_chat(model_name="gpt-4o-mini-2024-07-18", temperature=0)
        logger.info(f"Initialized utility model: {utility_llm}")
        
        embedding_llm = models.get_embedding_openai()
        # embedding_llm = models.get_ollama_embedding(model_name="nomic-embed-text")
        # embedding_llm = models.get_huggingface_embedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
        logger.info(f"Initialized embedding model: {embedding_llm}")

        big_brain_llm = models.get_anthropic_chat(model_name="claude-3-sonnet-20240229", temperature=0)  
        logger.info(f"Initialized BigBrain model: {big_brain_llm}")

        dreamteam_model1 = models.get_anthropic_chat(model_name="claude-3-sonnet-20240229", temperature=0)
        dreamteam_model2 = models.get_openai_chat(model_name="gpt-4", temperature=0)
        logger.info(f"Initialized DreamTeam models: {dreamteam_model1}, {dreamteam_model2}")

        logger.info("Setting up agent configuration...")
        config = AgentConfig(
            chat_model = chat_llm,
            utility_model = utility_llm,
            embeddings_model = embedding_llm,
            big_brain_model = big_brain_llm,
            dreamteam_model1 = dreamteam_model1,
            dreamteam_model2 = dreamteam_model2,
            memory_subdir = "",
            auto_memory_count = 0,
            auto_memory_skip = 2,
            rate_limit_seconds = 60,
            rate_limit_requests = 30,
            rate_limit_input_tokens = 0,
            rate_limit_output_tokens = 0,
            msgs_keep_max = 25,
            msgs_keep_start = 5,
            msgs_keep_end = 10,
            max_tool_response_length = 3000,
            response_timeout_seconds = 60,
            code_exec_docker_enabled = True,
            code_exec_docker_name = "agent-zero-exe",
            code_exec_docker_image = "frdel/agent-zero-exe:latest",
            code_exec_docker_ports = { "22/tcp": 50022 },
            code_exec_docker_volumes = { files.get_abs_path("work_dir"): {"bind": "/root", "mode": "rw"} },
            code_exec_ssh_enabled = True,
            code_exec_ssh_addr = "localhost",
            code_exec_ssh_port = 50022,
            code_exec_ssh_user = "root",
            code_exec_ssh_pass = "toor",
            additional = {},
        )
        
        logger.info("Creating agent...")
        agent0 = Agent(number = 0, config = config)
        return agent0
    except Exception as e:
        logger.error(f"Error in initialize: {str(e)}")
        logger.error(traceback.format_exc())
        raise

def chat(agent: Agent):
    """
    Main chat loop for interacting with the agent.
    
    :param agent: The initialized Agent instance
    """
    while True:
        try:
            with input_lock:
                timeout = agent.get_data("timeout")
                if not timeout:
                    PrintStyle(background_color="#6C3483", font_color="white", bold=True, padding=True).print(f"User message ('e' to leave):")        
                    import readline
                    user_input = input("> ")
                    PrintStyle(font_color="white", padding=False, log_only=True).print(f"> {user_input}") 
                else:
                    PrintStyle(background_color="#6C3483", font_color="white", bold=True, padding=True).print(f"User message ({timeout}s timeout, 'w' to wait, 'e' to leave):")        
                    import readline
                    user_input = timeout_input("> ", timeout=timeout)
                                        
                    if not user_input:
                        user_input = read_file("prompts/fw.msg_timeout.md")
                        PrintStyle(font_color="white", padding=False).stream(f"{user_input}")        
                    else:
                        user_input = user_input.strip()
                        if user_input.lower()=="w":
                            user_input = input("> ").strip()
                        PrintStyle(font_color="white", padding=False, log_only=True).print(f"> {user_input}")        
                        
            if user_input.lower() == 'e':
                logger.info("Exiting chat...")
                break

            logger.info("Processing user input...")
            try:
                if user_input.lower().startswith("!dreamteam"):
                    assistant_response = agent.process_dreamteam_request(user_input)
                else:
                    assistant_response = agent.message_loop(user_input)
                logger.info("Received response from agent")
            except Exception as e:
                logger.error(f"An error occurred: {str(e)}")
                logger.error(traceback.format_exc())
                assistant_response = f"An error occurred: {str(e)}"
            
            PrintStyle(font_color="white",background_color="#1D8348", bold=True, padding=True).print(f"{agent.agent_name}: response:")        
            PrintStyle(font_color="white").print(f"{assistant_response}")        
        except Exception as e:
            logger.error(f"Error in chat loop: {str(e)}")
            logger.error(traceback.format_exc())
            print(f"An error occurred in the chat loop: {str(e)}")

def intervention():
    """
    Handle user intervention during agent processing.
    """
    if Agent.streaming_agent and not Agent.paused:
        Agent.paused = True
        PrintStyle(background_color="#6C3483", font_color="white", bold=True, padding=True).print(f"User intervention ('e' to leave, empty to continue):")        

        import readline
        user_input = input("> ").strip()
        PrintStyle(font_color="white", padding=False, log_only=True).print(f"> {user_input}")        
        
        if user_input.lower() == 'e': os._exit(0)
        if user_input: Agent.streaming_agent.intervention_message = user_input
        Agent.paused = False

def capture_keys():
    """
    Capture key inputs for user intervention.
    """
    global input_lock
    intervent = False            
    while True:
        if intervent: intervention()
        intervent = False
        time.sleep(0.1)
        
        if Agent.streaming_agent:
            with input_lock, raw_input, application_keypad:
                event: InputEvent | None = get_input_event(timeout=0.1)
                if event and (event.shortcut.isalpha() or event.shortcut.isspace()):
                    intervent = True
                    continue

def timeout_input(prompt, timeout=10):
    """
    Get user input with a timeout.
    
    :param prompt: The prompt to display for input
    :param timeout: The timeout in seconds
    :return: The user input or None if timed out
    """
    return timed_input.timeout_input(prompt=prompt, timeout=timeout)

def run_terminal_mode():
    """
    Run the agent in terminal mode.
    """
    try:
        logger.info("Initializing framework...")
        threading.Thread(target=capture_keys, daemon=True).start()
        logger.info("Started key capture thread")
        agent0 = initialize()
        logger.info("Starting chat loop...")
        chat(agent0)
    except Exception as e:
        logger.error(f"An error occurred during initialization: {str(e)}")
        logger.error(traceback.format_exc())
    
    logger.info("Main script finished")

if __name__ == "__main__":
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "--gui":
            logger.info("Starting GUI mode...")
            from gui_wrapper import run_gui
            agent = initialize()
            run_gui(agent)
        else:
            logger.info("Starting terminal mode...")
            run_terminal_mode()
    except Exception as e:
        logger.error(f"Unhandled exception in main: {str(e)}")
        logger.error(traceback.format_exc())
        print(f"An unhandled exception occurred: {str(e)}")
        print("Please check the log file for more details.")
        sys.exit(1)