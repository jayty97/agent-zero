# agent_wrapper.py

import os
import shutil
from typing import Dict, Any, List
from PyQt6.QtCore import QObject, pyqtSignal
from agent import Agent, AgentConfig
import models
import logging

logger = logging.getLogger(__name__)

class AgentWrapper(QObject):
    message_processed = pyqtSignal(str)
    agent_output = pyqtSignal(str)

    def __init__(self, settings: Dict[str, Any]):
        super().__init__()
        self.settings = settings
        self.config = self.create_agent_config()
        self.main_agent = Agent(number=0, config=self.config)
        self.chat_history = []
        self.memory = {}
        self.work_dir = os.path.join(os.getcwd(), "work_dir")
        self.active_tools = {}

    def create_agent_config(self) -> AgentConfig:
        chat_model = self.get_model('Chat')
        utility_model = self.get_model('Utility')
        embedding_model = self.get_embedding_model()

        return AgentConfig(
            chat_model=chat_model,
            utility_model=utility_model,
            embeddings_model=embedding_model,
            code_exec_docker_enabled=True,
            code_exec_ssh_enabled=True,
        )

    def get_model(self, agent_type: str):
        company = self.settings['companies'][agent_type]
        model_name = self.settings['models'][agent_type]
        temperature = self.settings['temperatures'].get(agent_type, 0.7)

        model_function = getattr(models, f"get_{company.lower()}_chat", None)
        if model_function:
            return model_function(model_name=model_name, temperature=temperature)
        else:
            raise ValueError(f"Unsupported company: {company}")

    def get_embedding_model(self):
        company = self.settings['companies']['Embedding']
        model_name = self.settings['models']['Embedding']

        model_function = getattr(models, f"get_{company.lower()}_embedding", None)
        if model_function:
            return model_function(model_name=model_name)
        else:
            raise ValueError(f"Unsupported embedding company: {company}")

    def message_loop(self, message: str) -> str:
        os.chdir(self.work_dir)
        self.agent_output.emit(f"User: {message}\n")
        response = self.main_agent.message_loop(message)
        self.agent_output.emit(f"Agent 0: {response}\n")
        self.message_processed.emit(response)
        return response

    def call_bigbrain(self, message: str) -> str:
        bigbrain = self.main_agent.get_data("bigbrain")
        if bigbrain is None:
            bigbrain = Agent(self.main_agent.number + 1, self.config)
            bigbrain.set_data("superior", self.main_agent)
            self.main_agent.set_data("bigbrain", bigbrain)

        self.agent_output.emit(f"Agent 0 to BigBrain: {message}\n")
        response = bigbrain.message_loop(message)
        self.agent_output.emit(f"BigBrain to Agent 0: {response}\n")
        return response

    def call_dreamteam(self, message: str) -> str:
        dreamteam = self.main_agent.get_data("dreamteam")
        if dreamteam is None:
            dreamteam = [Agent(self.main_agent.number + 2, self.config), Agent(self.main_agent.number + 3, self.config)]
            for agent in dreamteam:
                agent.set_data("superior", self.main_agent)
            self.main_agent.set_data("dreamteam", dreamteam)

        self.agent_output.emit(f"Agent 0 to DreamTeam: {message}\n")
        response1 = dreamteam[0].message_loop(message)
        self.agent_output.emit(f"DreamTeam Agent 1 to Agent 0: {response1}\n")
        response2 = dreamteam[1].message_loop(f"{message}\n\nConsider this input as well: {response1}")
        self.agent_output.emit(f"DreamTeam Agent 2 to Agent 0: {response2}\n")
        combined_response = f"DreamTeam Response:\nAgent 1: {response1}\nAgent 2: {response2}"
        return combined_response

    def get_memory(self) -> Dict[str, Any]:
        return self.main_agent.get_data("memory") or {}

    def set_memory(self, memory: Dict[str, Any]):
        self.main_agent.set_data("memory", memory)

    def get_context_size(self) -> int:
        return len(self.main_agent.history)

    def set_work_dir(self, new_work_dir):
        self.work_dir = new_work_dir

    def save_file(self, file_name: str, content: str):
        file_path = os.path.join(self.work_dir, file_name)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def retrieve_file(self, file_name: str) -> str:
        file_path = os.path.join(self.work_dir, file_name)
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        return ""

    def list_files(self) -> List[str]:
        return os.listdir(self.work_dir)

    def delete_file(self, file_name: str):
        file_path = os.path.join(self.work_dir, file_name)
        if os.path.exists(file_path):
            os.remove(file_path)

    def copy_file(self, src_file: str, dst_file: str):
        src_path = os.path.join(self.work_dir, src_file)
        dst_path = os.path.join(self.work_dir, dst_file)
        shutil.copy2(src_path, dst_path)

    def activate_tool(self, tool_name: str, description: str):
        self.active_tools[tool_name] = description
        message = f"Tool '{tool_name}' has been activated. Description: {description}"
        self.agent_output.emit(message)
        self.message_loop(message)

    def deactivate_tool(self, tool_name: str):
        if tool_name in self.active_tools:
            del self.active_tools[tool_name]
            message = f"Tool '{tool_name}' has been deactivated."
            self.agent_output.emit(message)
            self.message_loop(message)

    def get_active_tools(self) -> str:
        if not self.active_tools:
            return "No tools are currently active."
        
        tool_list = "\n".join([f"- {name}: {desc}" for name, desc in self.active_tools.items()])
        return f"Active tools:\n{tool_list}"

    def execute_tool(self, tool_name: str, *args, **kwargs):
        if tool_name not in self.active_tools:
            return f"Error: Tool '{tool_name}' is not active."
        
        try:
            module = __import__(f"tools.{tool_name}", fromlist=['execute'])
            result = module.execute(*args, **kwargs)
            return f"Tool '{tool_name}' executed successfully. Result: {result}"
        except Exception as e:
            return f"Error executing tool '{tool_name}': {str(e)}"

    @staticmethod
    def get_available_models() -> Dict[str, List[str]]:
        return {
            "OpenAI": ["gpt-4o-2024-08-06", "gpt-4o-mini-2024-07-18", "gpt-4", "gpt-3.5-turbo"],
            "Anthropic": ["Claude 3.0", "Claude 3.5 Sonnet"],
            "Google": ["Gemini 1.5 Pro", "Gemini 1.5 Flash"],
            "Azure OpenAI": ["gpt-4o", "gpt-4 Turbo"],
            "Cohere": ["Command", "Rerank"],
            "Mistral": ["Mixtral 8x22B", "Mistral Large"],
            "Meta": ["Llama 3.1 405B"]
        }

    @staticmethod
    def get_available_embedding_models() -> Dict[str, List[str]]:
        return {
            "OpenAI": ["text-embedding-3-large", "text-embedding-3-small", "text-embedding-ada-002"],
            "Google": ["text-embedding-preview-0409", "text-multilingual-embedding-preview-0409"]
        }