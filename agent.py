from dataclasses import dataclass, field
import time
import importlib
import inspect
import os
import json
import sys
import traceback
from typing import Any, Optional, Dict, List
from python.helpers import extract_tools, rate_limiter, files, errors
from python.helpers.print_style import PrintStyle
from langchain.schema import AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.embeddings import Embeddings
import logging

logger = logging.getLogger(__name__)

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
    
    def __init__(self, number: int, config: AgentConfig):
        self.config = config       
        self.number = number
        self.agent_name = f"Agent {self.number}"
        self.system_prompt = files.read_file("./prompts/agent.system.md").replace("{", "{{").replace("}", "}}")
        self.tools_prompt = files.read_file("./prompts/agent.tools.md").replace("{", "{{").replace("}", "}}")
        self.history = []
        self.last_message = ""
        self.intervention_message = ""
        self.intervention_status = False
        self.rate_limiter = rate_limiter.RateLimiter(
            max_calls=self.config.rate_limit_requests,
            max_input_tokens=self.config.rate_limit_input_tokens,
            max_output_tokens=self.config.rate_limit_output_tokens,
            window_seconds=self.config.rate_limit_seconds
        )
        self.data = {}
        self.last_response_time = 0
        self.last_token_usage = 0
        self.memory_usage = 0
        os.chdir(files.get_abs_path("./work_dir"))

    def get_memory_context(self) -> str:
        return self.fetch_memories(True)

    def is_interruptible(self) -> bool:
        return True

    def interrupt_chat(self):
        self.intervention_message = "User interrupted the chat."
        self.intervention_status = True

    def process_bigbrain_request(self, query: str):
        if self.config.big_brain_model is None:
            return "BigBrain model is not configured."
        try:
            context = self.get_conversation_context()
            full_query = f"Conversation context:\n{context}\n\nNew query: {query}\n\nAs BigBrain, provide a comprehensive and insightful analysis."
            response = self.config.big_brain_model.invoke(full_query)
            bigbrain_response = self.process_big_brain_response(response)
            self.append_message(f"BigBrain: {bigbrain_response}")
            return f"I consulted with BigBrain, and here's what it says:\n\n{bigbrain_response}"
        except Exception as e:
            error_message = f"Error in BigBrain processing: {str(e)}"
            self.append_message(error_message, human=True)
            return error_message

    def process_big_brain_response(self, response):
        if hasattr(response, 'content'):
            response = response.content
        if isinstance(response, str) and response.startswith("BigBrain Analysis:"):
            response = response[len("BigBrain Analysis:"):].strip()
        return response

    def process_dreamteam_request(self, query: str):
        if self.config.dreamteam_model1 is None or self.config.dreamteam_model2 is None:
            return "DreamTeam models are not configured."
        try:
            context = self.get_conversation_context()
            full_query = f"Conversation context:\n{context}\n\nNew query: {query}\n\nCollaborate to solve this problem."
            
            response1 = self.config.dreamteam_model1.invoke(full_query)
            response1_content = self.extract_content(response1)
            self.append_message(f"DreamTeam Model 1: {response1_content}")
            
            full_query2 = f"{full_query}\n\nFirst model's response: {response1_content}\n\nProvide your perspective and build upon or critique the first response."
            response2 = self.config.dreamteam_model2.invoke(full_query2)
            response2_content = self.extract_content(response2)
            self.append_message(f"DreamTeam Model 2: {response2_content}")
            
            consolidated_response = self.consolidate_dreamteam_responses([response1_content, response2_content])
            self.append_message(f"DreamTeam Conclusion: {consolidated_response}")
            
            return f"After consulting with the DreamTeam, here's the consolidated conclusion:\n\n{consolidated_response}"
        except Exception as e:
            error_message = f"Error in DreamTeam processing: {str(e)}"
            self.append_message(error_message, human=True)
            return error_message

    def consolidate_dreamteam_responses(self, responses):
        consolidation_prompt = "Based on the DreamTeam's responses, provide a consolidated conclusion:"
        for i, response in enumerate(responses):
            consolidation_prompt += f"\n\nModel {i+1} response: {response}"
        
        consolidated_response = self.config.utility_model.invoke(consolidation_prompt)
        return self.extract_content(consolidated_response)

    def extract_content(self, response):
        return response.content if hasattr(response, 'content') else str(response)

    def message_loop(self, msg: str):
        try:
            printer = PrintStyle(italic=True, font_color="#b3ffd9", padding=False)    
            user_message = files.read_file("./prompts/fw.user_message.md", message=msg)
            self.append_message(user_message, human=True)
            memories = self.fetch_memories(True)
            
            max_iterations = 5  # Limit the number of iterations to prevent infinite loops
            iteration_count = 0
            start_time = time.time()

            while iteration_count < max_iterations:
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
                            break  # Exit the loop if the message is repeated
                        else:
                            self.append_message(agent_response)
                            tools_result = self.process_tools(agent_response)
                            if tools_result:
                                return tools_result
                            if self.is_query_complete(agent_response):
                                break  # Exit the loop if the query is deemed complete

                except Exception as e:
                    error_message = errors.format_error(e)
                    msg_response = files.read_file("./prompts/fw.error.md", error=error_message)
                    self.append_message(msg_response, human=True)
                    PrintStyle(font_color="red", padding=True).print(msg_response)
                    break  # Exit the loop on error

                iteration_count += 1

            end_time = time.time()
            self.last_response_time = end_time - start_time
            self.last_token_usage = self.rate_limiter.get_total_tokens()
            self.update_memory_usage()

            if iteration_count == max_iterations:
                return "I apologize, but I seem to be having trouble providing a complete answer. Let me know if you'd like me to try a different approach or if you have any other questions."

            return agent_response

        except Exception as e:
            error_message = f"Unexpected error in message_loop: {str(e)}"
            logger.error(error_message)
            logger.error(traceback.format_exc())
            return f"An unexpected error occurred: {error_message}"
        finally:
            Agent.streaming_agent = None

    def append_message(self, msg: str, human: bool = False):
        message_type = "human" if human else "ai"
        if self.history and self.history[-1].type == message_type:
            self.history[-1].content += "\n\n" + msg
        else:
            new_message = HumanMessage(content=msg) if human else AIMessage(content=msg)
            self.history.append(new_message)
            self.cleanup_history(self.config.msgs_keep_max, self.config.msgs_keep_start, self.config.msgs_keep_end)
        if message_type == "ai":
            self.last_message = msg

    def fetch_memories(self, reset_skip=False):
        if self.config.auto_memory_count <= 0:
            return ""
        if reset_skip:
            self.memory_skip_counter = 0

        if self.memory_skip_counter > 0:
            self.memory_skip_counter -= 1
            return ""
        else:
            self.memory_skip_counter = self.config.auto_memory_skip
            from python.tools import memory_tool
            messages = self.concat_messages(self.history)
            memories = memory_tool.search(self, messages)
            input = {
                "conversation_history": messages,
                "raw_memories": memories
            }
            cleanup_prompt = files.read_file("./prompts/msg.memory_cleanup.md").replace("{", "{{")       
            clean_memories = self.send_adhoc_message(cleanup_prompt, json.dumps(input), output_label="Memory injection")
            return clean_memories

    def concat_messages(self, messages):
        return "\n".join([f"{msg.type}: {msg.content}" for msg in messages])

    def get_conversation_context(self):
        # Return the last few messages from the conversation history
        context_messages = self.history[-5:]  # Adjust the number as needed
        return self.concat_messages(context_messages)

    def send_adhoc_message(self, system: str, msg: str, output_label: str):
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

    def replace_middle_messages(self,middle_messages):
        cleanup_prompt = files.read_file("./prompts/fw.msg_cleanup.md")
        summary = self.send_adhoc_message(system=cleanup_prompt,msg=self.concat_messages(middle_messages), output_label="Mid messages cleanup summary")
        new_human_message = HumanMessage(content=summary)
        return [new_human_message]

    def get_data(self, field:str):
        return self.data.get(field, None)

    def set_data(self, field:str, value):
        self.data[field] = value

    def get_last_response_time(self):
        return self.last_response_time

    def get_last_token_usage(self):
        return self.last_token_usage

    def get_memory_usage(self):
        return self.memory_usage

    def update_memory_usage(self):
        # This is a simplified method to estimate memory usage
        # In a real-world scenario, you might want to use a more accurate method
        self.memory_usage = sys.getsizeof(self.history) / 1024  # Convert to KB

    def get_context_size(self):
        # Estimate the context size based on the total characters in the history
        return sum(len(msg.content) for msg in self.history)

    def is_query_complete(self, response):
        # Implement logic to determine if the query has been sufficiently answered
        if len(response) > 500:  # Consider the response complete if it's longer than 500 characters
            return True
        if "In conclusion" in response or "To summarize" in response:
            return True
        return False