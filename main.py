import threading, time, models, os
from ansio import application_keypad, mouse_input, raw_input
from ansio.input import InputEvent, get_input_event
from agent import Agent, AgentConfig
from python.helpers.print_style import PrintStyle
from python.helpers.files import read_file
from python.helpers import files
import python.helpers.timed_input as timed_input

input_lock = threading.Lock()
os.chdir(files.get_abs_path("./work_dir"))

def initialize():
    print("Initializing models...")
    
    # main chat model used by agents (smarter, more accurate)
    # chat_llm = models.get_groq_llama70b(temperature=0.2)
    # chat_llm = models.get_groq_llama70b_json(temperature=0.2)
    # chat_llm = models.get_groq_llama8b(temperature=0.2)
    # chat_llm = models.get_openai_gpt35(temperature=0)
    # chat_llm = models.get_openai_gpt4(temperature=0)
    # chat_llm = models.get_openai_chat(temperature=0)
    chat_llm = models.get_openai_chat(model="gpt-4o-mini-2024-07-18", temperature=0)
    # chat_llm = models.get_anthropic_opus(temperature=0)
    # chat_llm = models.get_anthropic_sonnet(temperature=0)
    # chat_llm = models.get_anthropic_sonnet_35(temperature=0)
    # chat_llm = models.get_anthropic_haiku(temperature=0)
    # chat_llm = models.get_ollama_dolphin()
    # chat_llm = models.get_ollama(model_name="gemma2:27b")
    # chat_llm = models.get_ollama(model_name="llama3:8b-text-fp16")
    # chat_llm = models.get_ollama(model_name="gemma2:latest")
    # chat_llm = models.get_ollama(model_name="qwen:14b")
    # chat_llm = models.get_google_chat()
    print(f"Initialized chat model: {chat_llm}")

    # utility model used for helper functions (cheaper, faster)
    utility_llm = models.get_openai_chat(model="gpt-4o-mini-2024-07-18", temperature=0)
    print(f"Initialized utility model: {utility_llm}")
    
    # embedding model used for memory
    embedding_llm = models.get_embedding_openai()
    # embedding_llm = models.get_embedding_hf()
    print(f"Initialized embedding model: {embedding_llm}")

    # Initialize the BigBrain model (optional)
    big_brain_llm = models.get_anthropic_sonnet_35(temperature=0)  
    print(f"Initialized BigBrain model: {big_brain_llm}")

    # Initialize the DreamTeam models
    dreamteam_model1 = models.get_anthropic_sonnet_35(temperature=0)
    dreamteam_model2 = chat_llm = models.get_openai_gpt4(temperature=0)
    print(f"Initialized DreamTeam models: {dreamteam_model1}, {dreamteam_model2}")

    print("Setting up agent configuration...")
    config = AgentConfig(
        chat_model = chat_llm,
        utility_model = utility_llm,
        embeddings_model = embedding_llm,
        big_brain_model = big_brain_llm,
        dreamteam_model1 = dreamteam_model1,
        dreamteam_model2 = dreamteam_model2,
        # memory_subdir = "",
        auto_memory_count = 0,
        # auto_memory_skip = 2,
        # rate_limit_seconds = 60,
        # rate_limit_requests = 30,
        # rate_limit_input_tokens = 0,
        # rate_limit_output_tokens = 0,
        # msgs_keep_max = 25,
        # msgs_keep_start = 5,
        # msgs_keep_end = 10,
        # max_tool_response_length = 3000,
        # response_timeout_seconds = 60,
        code_exec_docker_enabled = True,
        # code_exec_docker_name = "agent-zero-exe",
        # code_exec_docker_image = "frdel/agent-zero-exe:latest",
        # code_exec_docker_ports = { "22/tcp": 50022 }
        # code_exec_docker_volumes = { files.get_abs_path("work_dir"): {"bind": "/root", "mode": "rw"} }
        code_exec_ssh_enabled = True,
        # code_exec_ssh_addr = "localhost",
        # code_exec_ssh_port = 50022,
        # code_exec_ssh_user = "root",
        # code_exec_ssh_pass = "toor",
        # additional = {},
    )
    
    print("Creating agent...")
    agent0 = Agent(number = 0, config = config)
    print("Starting chat loop...")
    chat(agent0)

def chat(agent:Agent):
    while True:
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
            print("Exiting chat...")
            break

        print("Processing user input...")
        try:
            assistant_response = agent.message_loop(user_input)
            print("Received response from agent")
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            assistant_response = f"An error occurred: {str(e)}"
        
        PrintStyle(font_color="white",background_color="#1D8348", bold=True, padding=True).print(f"{agent.agent_name}: response:")        
        PrintStyle(font_color="white").print(f"{assistant_response}")        

def intervention():
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
        global input_lock
        intervent=False            
        while True:
            if intervent: intervention()
            intervent = False
            time.sleep(0.1)
            
            if Agent.streaming_agent:
                with input_lock, raw_input, application_keypad:
                    event: InputEvent | None = get_input_event(timeout=0.1)
                    if event and (event.shortcut.isalpha() or event.shortcut.isspace()):
                        intervent=True
                        continue

def timeout_input(prompt, timeout=10):
    return timed_input.timeout_input(prompt=prompt, timeout=timeout)

if __name__ == "__main__":
    print("Initializing framework...")
    threading.Thread(target=capture_keys, daemon=True).start()
    print("Started key capture thread")
    try:
        initialize()
    except Exception as e:
        print(f"An error occurred during initialization: {str(e)}")
    
    print("Main script finished")