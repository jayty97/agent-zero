from dataclasses import dataclass, field
import time, importlib, inspect, os, json, sys
from typing import Any, Optional, Dict, List
from python.helpers import extract_tools, rate_limiter, files, errors
from python.helpers.print_style import PrintStyle
from langchain.schema import AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.embeddings import Embeddings

@dataclass
class AgentConfig: 
    chat_model: BaseChatModel
    utility_model: BaseChatModel
    embeddings_model: Embeddings
    big_brain_model: Optional[BaseChatModel] = None
    dreamteam_model1: Optional[BaseChatModel] = None
    dreamteam_model2: Optional[BaseChatModel] = None
    memory_subdir: str = ""
    auto_memory_count: int = 3
    auto_memory_skip: int = 2
    rate_limit_seconds: int = 60
    rate_limit_requests: int = 15
    rate_limit_input_tokens: int = 1000000
    rate_limit_output_tokens: int = 0
    msgs_keep_max: int = 25
    msgs_keep_start: int = 5
    msgs_keep_end: int = 10
    response_timeout_seconds: int = 60
    max_tool_response_length: int = 3000
    code_exec_docker_enabled: bool = True
    code_exec_docker_name: str = "agent-zero-exe"
    code_exec_docker_image: str = "frdel/agent-zero-exe:latest"
    code_exec_docker_ports: dict[str,int] = field(default_factory=lambda: {"22/tcp": 50022})
    code_exec_docker_volumes: dict[str, dict[str, str]] = field(default_factory=lambda: {files.get_abs_path("work_dir"): {"bind": "/root", "mode": "rw"}})
    code_exec_ssh_enabled: bool = True
    code_exec_ssh_addr: str = "localhost"
    code_exec_ssh_port: int = 50022
    code_exec_ssh_user: str = "root"
    code_exec_ssh_pass: str = "toor"
    additional: Dict[str, Any] = field(default_factory=dict)

class Agent:
    paused = False
    streaming_agent = None
    
    def __init__(self, number:int, config: AgentConfig):
        self.config = config       
        self.number = number
        self.agent_name = f"Agent {self.number}"
        self.system_prompt = files.read_file("./prompts/agent.system.md").replace("{", "{{").replace("}", "}}")
        self.tools_prompt = files.read_file("./prompts/agent.tools.md").replace("{", "{{").replace("}", "}}")
        self.history = []
        self.last_message = ""
        self.intervention_message = ""
        self.intervention_status = False
        self.rate_limiter = rate_limiter.RateLimiter(max_calls=self.config.rate_limit_requests,max_input_tokens=self.config.rate_limit_input_tokens,max_output_tokens=self.config.rate_limit_output_tokens,window_seconds=self.config.rate_limit_seconds)
        self.data = {}
        os.chdir(files.get_abs_path("./work_dir"))

    def get_memory_context(self) -> str:
        return self.fetch_memories(True)

    def is_interruptible(self) -> bool:
        return True

    def process_dreamteam_request(self, query: str):
        if self.config.dreamteam_model1 is None or self.config.dreamteam_model2 is None:
            return None
        if "consult dreamteam" in query.lower():
            actual_query = query.lower().replace("consult dreamteam", "").strip()
            dreamteam_response = self.consult_dreamteam(actual_query)
            return f"DreamTeam Response:\n{dreamteam_response}"
        elif query.lower().startswith("!dreamteam"):
            actual_query = query[10:].strip()
            dreamteam_response = self.consult_dreamteam(actual_query)
            return f"DreamTeam Response:\n{dreamteam_response}"
        return None

    def consult_dreamteam(self, query: str):
        try:
            PrintStyle(bold=True, font_color="blue").print(f"Creating DreamTeam for query: {query}")
            dreamteam = self.create_dreamteam()
            PrintStyle(font_color="blue").print(f"DreamTeam created with models: {dreamteam.model1}, {dreamteam.model2}")
            
            PrintStyle(bold=True, font_color="blue").print("Sending query to DreamTeam")
            response = dreamteam.collaborate(query)
            
            return response
        except Exception as e:
            error_message = f"Error during DreamTeam consultation: {str(e)}"
            PrintStyle(font_color="red").print(error_message)
            return self.handle_dreamteam_error(error_message)

    def create_dreamteam(self):
        return DreamTeam(self.config.dreamteam_model1, self.config.dreamteam_model2, self)

    def handle_dreamteam_error(self, error_message: str):
        fallback_response = f"I encountered an issue while consulting the DreamTeam: {error_message}. " \
                            f"I'll proceed with my own analysis to the best of my abilities."
        self.append_message(fallback_response)
        return fallback_response
    
    def process_bigbrain_request(self, query: str):
        if self.config.big_brain_model is None:
            return None
        if "consult bigbrain" in query.lower():
            actual_query = query.lower().replace("consult bigbrain", "").strip()
            big_brain_response = self.consult_big_brain(actual_query)
            return f"BigBrain Agent Response:\n{big_brain_response}"
        elif query.lower().startswith("!bigbrain"):
            actual_query = query[9:].strip()
            big_brain_response = self.consult_big_brain(actual_query)
            return f"BigBrain Agent Response:\n{big_brain_response}"
        return None

    def consult_big_brain(self, query: str):
        try:
            PrintStyle(bold=True, font_color="blue").print(f"Creating BigBrainAgent for query: {query}")
            big_brain_agent = self.create_big_brain_agent()
            PrintStyle(font_color="blue").print(f"BigBrainAgent created with model: {big_brain_agent.config.chat_model}")
            
            # Get the full conversation history
            full_history = self.concat_messages(self.history)
            
            # Combine the full history with the new query
            full_query = f"Previous conversation:\n{full_history}\n\nNew query: {query}\n\nPlease analyze the context and answer the query."
            
            PrintStyle(bold=True, font_color="blue").print("Sending query to BigBrainAgent")
            response = big_brain_agent.message_loop(full_query)
            PrintStyle(font_color="blue").print(f"Received response from BigBrainAgent: {response[:100]}...")  # Log first 100 chars
            
            processed_response = self.process_big_brain_response(response)
            PrintStyle(font_color="blue").print(f"Processed BigBrain response: {processed_response[:100]}...")  # Log first 100 chars
            
            return processed_response
        except Exception as e:
            error_message = f"Error during BigBrain consultation: {str(e)}"
            PrintStyle(font_color="red").print(error_message)
            return self.handle_big_brain_error(error_message)

    def process_big_brain_response(self, response: str):
        # Remove any potential "BigBrain Analysis:" prefix from the response
        if response.startswith("BigBrain Analysis:"):
            response = response[len("BigBrain Analysis:"):].strip()
        return response

    def handle_big_brain_error(self, error_message: str):
        fallback_response = f"I encountered an issue while consulting the BigBrain Agent: {error_message}. " \
                            f"I'll proceed with my own analysis to the best of my abilities."
        self.append_message(fallback_response)
        return fallback_response

    def create_big_brain_agent(self):
        big_brain_config = AgentConfig(
            chat_model=self.config.big_brain_model,
            utility_model=self.config.utility_model,
            embeddings_model=self.config.embeddings_model,
            big_brain_model=None,  # Prevent recursive BigBrain creation
            memory_subdir=self.config.memory_subdir,
            auto_memory_count=self.config.auto_memory_count,
            auto_memory_skip=self.config.auto_memory_skip,
            rate_limit_seconds=self.config.rate_limit_seconds,
            rate_limit_requests=self.config.rate_limit_requests,
            rate_limit_input_tokens=self.config.rate_limit_input_tokens,
            rate_limit_output_tokens=self.config.rate_limit_output_tokens,
            msgs_keep_max=self.config.msgs_keep_max,
            msgs_keep_start=self.config.msgs_keep_start,
            msgs_keep_end=self.config.msgs_keep_end,
            response_timeout_seconds=self.config.response_timeout_seconds,
            max_tool_response_length=self.config.max_tool_response_length,
            code_exec_docker_enabled=self.config.code_exec_docker_enabled,
            code_exec_docker_name=self.config.code_exec_docker_name,
            code_exec_docker_image=self.config.code_exec_docker_image,
            code_exec_docker_ports=self.config.code_exec_docker_ports,
            code_exec_docker_volumes=self.config.code_exec_docker_volumes,
            code_exec_ssh_enabled=self.config.code_exec_ssh_enabled,
            code_exec_ssh_addr=self.config.code_exec_ssh_addr,
            code_exec_ssh_port=self.config.code_exec_ssh_port,
            code_exec_ssh_user=self.config.code_exec_ssh_user,
            code_exec_ssh_pass=self.config.code_exec_ssh_pass,
            additional=self.config.additional
        )
        return BigBrainAgent(number=self.number + 1, config=big_brain_config)

    def message_loop(self, msg: str):
        try:
            if msg.lower().startswith("code task:"):
                return self.handle_coding_task(msg[10:].strip())
            
            printer = PrintStyle(italic=True, font_color="#b3ffd9", padding=False)    
            user_message = files.read_file("./prompts/fw.user_message.md", message=msg)
            self.append_message(user_message, human=True)
            memories = self.fetch_memories(True)
            
            bigbrain_response = self.process_bigbrain_request(msg)
            if bigbrain_response:
                PrintStyle(font_color="white",background_color="#1D8348", bold=True, padding=True).print(f"{self.agent_name}: response:")        
                PrintStyle(font_color="white").print(bigbrain_response)
                return bigbrain_response
            
            dreamteam_response = self.process_dreamteam_request(msg)
            if dreamteam_response:
                PrintStyle(font_color="white",background_color="#1D8348", bold=True, padding=True).print(f"{self.agent_name}: response:")        
                PrintStyle(font_color="white").print(dreamteam_response)
                return dreamteam_response
            
            while True:
                Agent.streaming_agent = self
                agent_response = ""
                self.intervention_status = False

                try:
                    system = self.system_prompt + "\n\n" + self.tools_prompt
                    memories = self.fetch_memories()
                    if memories: system += "\n\n" + memories

                    prompt = ChatPromptTemplate.from_messages([
                        SystemMessage(content=system),
                        MessagesPlaceholder(variable_name="messages") ])
                    
                    inputs = {"messages": self.history}
                    chain = prompt | self.config.chat_model

                    formatted_inputs = prompt.format(messages=self.history)
                    tokens = int(len(formatted_inputs)/4)     
                    self.rate_limiter.limit_call_and_input(tokens)
                    
                    PrintStyle(bold=True, font_color="green", padding=True, background_color="white").print(f"{self.agent_name}: Starting a message:")
                                            
                    for chunk in chain.stream(inputs):
                        if self.handle_intervention(agent_response): break

                        if isinstance(chunk, str): content = chunk
                        elif hasattr(chunk, "content"): content = str(chunk.content)
                        else: content = str(chunk)
                        
                        if content:
                            printer.stream(content)
                            agent_response += content

                    self.rate_limiter.set_output_tokens(int(len(agent_response)/4))
                    
                    if not self.handle_intervention(agent_response):
                        if self.last_message == agent_response:
                            self.append_message(agent_response)
                            warning_msg = files.read_file("./prompts/fw.msg_repeat.md")
                            self.append_message(warning_msg, human=True)
                            PrintStyle(font_color="orange", padding=True).print(warning_msg)
                        else:
                            self.append_message(agent_response)
                            tools_result = self.process_tools(agent_response)
                            if tools_result: return tools_result

                except Exception as e:
                    error_message = errors.format_error(e)
                    msg_response = files.read_file("./prompts/fw.error.md", error=error_message)
                    self.append_message(msg_response, human=True)
                    PrintStyle(font_color="red", padding=True).print(msg_response)
                    
        finally:
            Agent.streaming_agent = None

    def handle_coding_task(self, task_description: str):
        coding_prompt = files.read_file("./prompts/coding_task.md")
        full_prompt = f"{coding_prompt}\n\nTask Description: {task_description}\n\nPlease provide a solution based on the guidelines above."
        
        if self.config.dreamteam_model1 and self.config.dreamteam_model2:
            return self.consult_dreamteam(full_prompt)
        elif self.config.big_brain_model:
            return self.consult_big_brain(full_prompt)
        else:
            return self.message_loop(full_prompt)

    def get_data(self, field:str):
        return self.data.get(field, None)

    def set_data(self, field:str, value):
        self.data[field] = value

    def append_message(self, msg: str, human: bool = False):
        message_type = "human" if human else "ai"
        if self.history and self.history[-1].type == message_type:
            self.history[-1].content += "\n\n" + msg
        else:
            new_message = HumanMessage(content=msg) if human else AIMessage(content=msg)
            self.history.append(new_message)
            self.cleanup_history(self.config.msgs_keep_max, self.config.msgs_keep_start, self.config.msgs_keep_end)
        if message_type=="ai":
            self.last_message = msg

    def concat_messages(self,messages):
        return "\n".join([f"{msg.type}: {msg.content}" for msg in messages])

    def send_adhoc_message(self, system: str, msg: str, output_label:str):
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=system),
            HumanMessage(content=msg)])

        chain = prompt | self.config.utility_model
        response = ""
        printer = None

        if output_label:
            PrintStyle(bold=True, font_color="orange", padding=True, background_color="white").print(f"{self.agent_name}: {output_label}:")
            printer = PrintStyle(italic=True, font_color="orange", padding=False)                

        formatted_inputs = prompt.format()
        tokens = int(len(formatted_inputs)/4)     
        self.rate_limiter.limit_call_and_input(tokens)
    
        for chunk in chain.stream({}):
            if self.handle_intervention(): break

            if isinstance(chunk, str): content = chunk
            elif hasattr(chunk, "content"): content = str(chunk.content)
            else: content = str(chunk)

            if printer: printer.stream(content)
            response += content

        self.rate_limiter.set_output_tokens(int(len(response)/4))

        return response
            
    def get_last_message(self):
        if self.history:
            return self.history[-1]

    def replace_middle_messages(self,middle_messages):
        cleanup_prompt = files.read_file("./prompts/fw.msg_cleanup.md")
        summary = self.send_adhoc_message(system=cleanup_prompt,msg=self.concat_messages(middle_messages), output_label="Mid messages cleanup summary")
        new_human_message = HumanMessage(content=summary)
        return [new_human_message]

    def cleanup_history(self, max:int, keep_start:int, keep_end:int):
        if len(self.history) <= max:
            return self.history

        first_x = self.history[:keep_start]
        last_y = self.history[-keep_end:]
        middle_part = self.history[keep_start:-keep_end]

        if middle_part and middle_part[0].type != "human":
            if len(first_x) > 0:
                middle_part.insert(0, first_x.pop())

        if len(middle_part) % 2 == 0:
            middle_part = middle_part[:-1]

        new_middle_part = self.replace_middle_messages(middle_part)

        self.history = first_x + new_middle_part + last_y

        return self.history

    def handle_intervention(self, progress:str="") -> bool:
        while self.paused: time.sleep(0.1)
        if self.intervention_message and not self.intervention_status:
            if progress.strip(): self.append_message(progress)
            user_msg = files.read_file("./prompts/fw.intervention.md", user_message=self.intervention_message)
            self.append_message(user_msg,human=True)
            self.intervention_message = ""
            self.intervention_status = True
        return self.intervention_status

    def process_tools(self, msg: str):
        tool_request = extract_tools.json_parse_dirty(msg)

        if tool_request is not None:
            tool_name = tool_request.get("tool_name", "")
            tool_args = tool_request.get("tool_args", {})

            tool = self.get_tool(
                        tool_name,
                        tool_args,
                        msg)
                
            if self.handle_intervention(): return
            tool.before_execution(**tool_args)
            if self.handle_intervention(): return
            response = tool.execute(**tool_args)
            if self.handle_intervention(): return
            tool.after_execution(response)
            if self.handle_intervention(): return
            if response.break_loop: return response.message
        else:
            msg = files.read_file("prompts/fw.msg_misformat.md")
            self.append_message(msg, human=True)
            PrintStyle(font_color="red", padding=True).print(msg)

    def get_tool(self, name: str, args: dict, message: str, **kwargs):
        from python.tools.unknown import Unknown 
        from python.helpers.tool import Tool
        
        tool_class = Unknown
        if files.exists("python/tools",f"{name}.py"): 
            module = importlib.import_module("python.tools." + name)
            class_list = inspect.getmembers(module, inspect.isclass)

            for cls in class_list:
                if cls[1] is not Tool and issubclass(cls[1], Tool):
                    tool_class = cls[1]
                    break

        return tool_class(agent=self, name=name, args=args, message=message, **kwargs)

    def fetch_memories(self,reset_skip=False):
        if self.config.auto_memory_count<=0: return ""
        if reset_skip: self.memory_skip_counter = 0

        if self.memory_skip_counter > 0:
            self.memory_skip_counter-=1
            return ""
        else:
            self.memory_skip_counter = self.config.auto_memory_skip
            from python.tools import memory_tool
            messages = self.concat_messages(self.history)
            memories = memory_tool.search(self,messages)
            input = {
                "conversation_history" : messages,
                "raw_memories": memories
            }
            cleanup_prompt = files.read_file("./prompts/msg.memory_cleanup.md").replace("{", "{{")       
            clean_memories = self.send_adhoc_message(cleanup_prompt,json.dumps(input), output_label="Memory injection")
            return clean_memories

    def call_extension(self, name: str, **kwargs) -> Any:
        pass

class BigBrainAgent(Agent):
    def __init__(self, number: int, config: AgentConfig):
        super().__init__(number, config)
        self.agent_name = f"BigBrain Agent {self.number}"
        self.system_prompt = files.read_file("./prompts/bigbrain.system.md").replace("{", "{{").replace("}", "}}")
        print(f"Initialized BigBrainAgent with model: {self.config.chat_model}")

    def message_loop(self, msg: str):
        print(f"BigBrainAgent received message: {msg}")
        response = super().message_loop(msg)
        print(f"BigBrainAgent response: {response[:100]}...")  # Log first 100 chars
        return response

class DreamTeam:
    def __init__(self, model1: BaseChatModel, model2: BaseChatModel, agent: Agent):
        self.model1 = model1
        self.model2 = model2
        self.agent = agent
        self.conversation_history: List[Dict[str, Any]] = []

    def collaborate(self, query: str, max_turns: int = 3) -> str:
        self.conversation_history = []
        context = self.agent.get_memory_context()
        query_with_context = f"Context:\n{context}\n\nQuery: {query}"
        self._add_to_history("Human", query_with_context)
        
        PrintStyle(bold=True, font_color="cyan").print(f"DreamTeam Collaboration on query: {query}\n")

        for turn in range(max_turns):
            if self.agent.is_interruptible() and self.agent.handle_intervention():
                break

            PrintStyle(bold=True, font_color="yellow").print(f"Model 1 (Turn {turn + 1}) thinking", end='')
            self._animate_thinking()
            response1 = self._get_model_response(self.model1, f"Model 1 (Turn {turn + 1})")
            print("\r" + " " * 50 + "\r", end='')  # Clear the thinking animation
            self._add_to_history("Model 1", response1)
            PrintStyle(bold=True, font_color="yellow").print(f"Model 1 (Turn {turn + 1}):")
            PrintStyle(font_color="yellow").print(f"{response1}\n")

            if self.agent.is_interruptible() and self.agent.handle_intervention():
                break

            PrintStyle(bold=True, font_color="green").print(f"Model 2 (Turn {turn + 1}) thinking", end='')
            self._animate_thinking()
            response2 = self._get_model_response(self.model2, f"Model 2 (Turn {turn + 1})")
            print("\r" + " " * 50 + "\r", end='')  # Clear the thinking animation
            self._add_to_history("Model 2", response2)
            PrintStyle(bold=True, font_color="green").print(f"Model 2 (Turn {turn + 1}):")
            PrintStyle(font_color="green").print(f"{response2}\n")

            if self._is_conversation_complete():
                break

        PrintStyle(bold=True, font_color="magenta").print("Generating final response", end='')
        self._animate_thinking()
        final_response = self._generate_final_response()
        print("\r" + " " * 50 + "\r", end='')  # Clear the thinking animation
        PrintStyle(bold=True, font_color="magenta").print("Final Response:")
        PrintStyle(font_color="magenta").print(f"{final_response}\n")

        return final_response

    def _animate_thinking(self):
        for _ in range(3):
            for c in ['.', '..', '...']:
                sys.stdout.write(c)
                sys.stdout.flush()
                time.sleep(0.5)
                sys.stdout.write('\b' * len(c))

    def _get_model_response(self, model: BaseChatModel, role: str) -> str:
        prompt = self._generate_prompt(role)
        try:
            response = model.invoke(prompt)
            return response.content if hasattr(response, 'content') else str(response)
        except Exception as e:
            error_msg = f"Error getting response from {role}: {str(e)}"
            PrintStyle(font_color="red").print(error_msg)
            return f"Error: {str(e)}"

    def _generate_prompt(self, role: str) -> str:
        prompt = "You are part of a DreamTeam collaboration. Review the conversation history and provide your insights:\n\n"
        for entry in self.conversation_history:
            prompt += f"{entry['role']}: {entry['content']}\n\n"
        prompt += f"{role}: "
        return prompt

    def _add_to_history(self, role: str, content: str):
        self.conversation_history.append({"role": role, "content": content})

    def _is_conversation_complete(self) -> bool:
        if len(self.conversation_history) < 2:
            return False
        last_response = self.conversation_history[-1]['content'].lower()
        return "final answer" in last_response or "conclusion" in last_response

    def _generate_final_response(self) -> str:
        final_prompt = "Based on the conversation, provide a concise final answer or conclusion:\n\n"
        for entry in self.conversation_history:
            final_prompt += f"{entry['role']}: {entry['content']}\n\n"
        final_prompt += "Final Answer: "
        
        try:
            final_response = self.model1.invoke(final_prompt)
            return final_response.content if hasattr(final_response, 'content') else str(final_response)
        except Exception as e:
            error_msg = f"Error generating final response: {str(e)}"
            PrintStyle(font_color="red").print(error_msg)
            return f"Error generating final response: {str(e)}"

# Debugging function
def debug_print(message: str):
    print(f"[DEBUG] {message}")

# Add debug prints to key functions
def add_debug_prints():
    original_message_loop = Agent.message_loop
    def message_loop_with_debug(self, msg: str):
        debug_print(f"Entering message_loop with message: {msg[:50]}...")
        result = original_message_loop(self, msg)
        debug_print(f"Exiting message_loop with result: {str(result)[:50]}...")
        return result
    Agent.message_loop = message_loop_with_debug

    original_process_bigbrain_request = Agent.process_bigbrain_request
    def process_bigbrain_request_with_debug(self, query: str):
        debug_print(f"Processing BigBrain request: {query[:50]}...")
        result = original_process_bigbrain_request(self, query)
        debug_print(f"BigBrain request result: {str(result)[:50]}...")
        return result
    Agent.process_bigbrain_request = process_bigbrain_request_with_debug

    original_process_dreamteam_request = Agent.process_dreamteam_request
    def process_dreamteam_request_with_debug(self, query: str):
        debug_print(f"Processing DreamTeam request: {query[:50]}...")
        result = original_process_dreamteam_request(self, query)
        debug_print(f"DreamTeam request result: {str(result)[:50]}...")
        return result
    Agent.process_dreamteam_request = process_dreamteam_request_with_debug

# Uncomment the following line to enable debug prints
# add_debug_prints()