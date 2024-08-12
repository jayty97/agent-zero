import json
import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QComboBox,
                             QPushButton, QDoubleSpinBox, QGroupBox, QTabWidget,
                             QTextEdit, QFileDialog, QMessageBox, QDialog, QLabel)
from PyQt6.QtCore import Qt, pyqtSignal
from dotenv import load_dotenv, set_key

class APIKeyDialog(QDialog):
    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.service = service
        self.setWindowTitle(f"Enter API Key for {service}")
        self.setGeometry(100, 100, 400, 100)
        layout = QVBoxLayout(self)
        self.key_input = QTextEdit()
        layout.addWidget(QLabel(f"Enter API Key for {service}:"))
        layout.addWidget(self.key_input)
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_key)
        layout.addWidget(save_button)

    def save_key(self):
        key = self.key_input.toPlainText().strip()
        if key:
            set_key('.env', f"API_KEY_{self.service.upper()}", key)
            self.accept()
        else:
            QMessageBox.warning(self, "Invalid Input", "Please enter a valid API key.")

class SettingsPanel(QWidget):
    settings_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.settings_file = "settings.json"
        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        # Models tab
        models_tab = QWidget()
        models_layout = QVBoxLayout(models_tab)
        self.setup_models_ui(models_layout)
        tabs.addTab(models_tab, "Models")

        # API Keys tab
        api_keys_tab = QWidget()
        api_keys_layout = QVBoxLayout(api_keys_tab)
        self.setup_api_keys_ui(api_keys_layout)
        tabs.addTab(api_keys_tab, "API Keys")

        layout.addWidget(tabs)
        self.save_button = QPushButton("Save Settings")
        self.save_button.clicked.connect(self.save_settings)
        layout.addWidget(self.save_button)

    def setup_models_ui(self, layout):
        self.company_selections = {}
        self.model_selections = {}

        company_models = {
            "OpenAI": ["gpt-4o-2024-08-06", "gpt-4o-mini-2024-07-18", "gpt-4", "gpt-3.5-turbo"],
            "Anthropic": ["Claude 3.0", "Claude 3.5 Sonnet"],
            "Google": ["Gemini 1.5 Pro", "Gemini 1.5 Flash"],
            "Azure OpenAI": ["gpt-4o", "gpt-4 Turbo"],
            "Cohere": ["Command", "Rerank"],
            "Mistral": ["Mixtral 8x22B", "Mistral Large"],
            "Meta": ["Llama 3.1 405B"]
        }

        embedding_models = {
            "OpenAI": ["text-embedding-3-large", "text-embedding-3-small", "text-embedding-ada-002"],
            "Google": ["text-embedding-preview-0409", "text-multilingual-embedding-preview-0409"]
        }

        for agent_name in ["Chat", "Utility", "BigBrain", "DreamTeam1", "DreamTeam2"]:
            group = QGroupBox(agent_name)
            group_layout = QFormLayout()

            company_combo = QComboBox()
            company_combo.addItems(company_models.keys())
            company_combo.currentTextChanged.connect(lambda _, a=agent_name: self.update_model_list(a))
            group_layout.addRow(f"{agent_name} Company:", company_combo)
            self.company_selections[agent_name] = company_combo

            model_combo = QComboBox()
            group_layout.addRow(f"{agent_name} Model:", model_combo)
            self.model_selections[agent_name] = model_combo

            temp_spin = QDoubleSpinBox()
            temp_spin.setRange(0.0, 1.0)
            temp_spin.setSingleStep(0.1)
            temp_spin.setValue(0.7)  # Default temperature
            group_layout.addRow("Temperature:", temp_spin)
            self.model_selections[f"{agent_name}_temp"] = temp_spin

            group.setLayout(group_layout)
            layout.addWidget(group)

            self.update_model_list(agent_name)

        # Embedding model setup
        embedding_group = QGroupBox("Embedding")
        embedding_layout = QFormLayout()

        embedding_company_combo = QComboBox()
        embedding_company_combo.addItems(embedding_models.keys())
        embedding_company_combo.currentTextChanged.connect(self.update_embedding_model_list)
        embedding_layout.addRow("Embedding Company:", embedding_company_combo)
        self.company_selections["Embedding"] = embedding_company_combo

        embedding_model_combo = QComboBox()
        embedding_layout.addRow("Embedding Model:", embedding_model_combo)
        self.model_selections["Embedding"] = embedding_model_combo

        embedding_group.setLayout(embedding_layout)
        layout.addWidget(embedding_group)

        self.update_embedding_model_list()

    def setup_api_keys_ui(self, layout):
        services = ["OpenAI", "Anthropic", "Google", "Azure OpenAI", "Cohere", "Mistral", "Meta", "Perplexity"]
        for service in services:
            button = QPushButton(f"Set {service} API Key")
            button.clicked.connect(lambda _, s=service: self.set_api_key(s))
            layout.addWidget(button)

    def set_api_key(self, service):
        dialog = APIKeyDialog(service, self)
        if dialog.exec():
            QMessageBox.information(self, "Success", f"{service} API key has been saved to .env file")
            self.refresh_model_lists()

    def update_model_list(self, agent_name):
        company = self.company_selections[agent_name].currentText()
        model_combo = self.model_selections[agent_name]
        model_combo.clear()
        model_combo.addItems(self.get_models_for_company(company))

    def update_embedding_model_list(self):
        company = self.company_selections["Embedding"].currentText()
        model_combo = self.model_selections["Embedding"]
        model_combo.clear()
        model_combo.addItems(self.get_embedding_models_for_company(company))

    def get_models_for_company(self, company):
        company_models = {
            "OpenAI": ["gpt-4o-2024-08-06", "gpt-4o-mini-2024-07-18", "gpt-4", "gpt-3.5-turbo"],
            "Anthropic": ["Claude 3.0", "Claude 3.5 Sonnet"],
            "Google": ["Gemini 1.5 Pro", "Gemini 1.5 Flash"],
            "Azure OpenAI": ["gpt-4o", "gpt-4 Turbo"],
            "Cohere": ["Command", "Rerank"],
            "Mistral": ["Mixtral 8x22B", "Mistral Large"],
            "Meta": ["Llama 3.1 405B"]
        }
        return company_models.get(company, [])

    def get_embedding_models_for_company(self, company):
        embedding_models = {
            "OpenAI": ["text-embedding-3-large", "text-embedding-3-small", "text-embedding-ada-002"],
            "Google": ["text-embedding-preview-0409", "text-multilingual-embedding-preview-0409"]
        }
        return embedding_models.get(company, [])

    def save_settings(self):
        settings = {
            "companies": {agent_name: combo.currentText() for agent_name, combo in self.company_selections.items()},
            "models": {agent_name: combo.currentText() for agent_name, combo in self.model_selections.items() if not agent_name.endswith('_temp')},
            "temperatures": {agent_name: self.model_selections[f"{agent_name}_temp"].value() for agent_name in self.model_selections.keys() if not agent_name.endswith('_temp') and agent_name != "Embedding"},
        }

        with open(self.settings_file, 'w') as f:
            json.dump(settings, f)
        QMessageBox.information(self, "Settings Saved", "All settings have been saved successfully.")
        self.settings_changed.emit()

    def load_settings(self):
        try:
            with open(self.settings_file, 'r') as f:
                settings = json.load(f)
            for agent_name, company_name in settings.get("companies", {}).items():
                if agent_name in self.company_selections:
                    index = self.company_selections[agent_name].findText(company_name)
                    if index >= 0:
                        self.company_selections[agent_name].setCurrentIndex(index)
            for agent_name, model_name in settings.get("models", {}).items():
                if agent_name in self.model_selections:
                    index = self.model_selections[agent_name].findText(model_name)
                    if index >= 0:
                        self.model_selections[agent_name].setCurrentIndex(index)
            for agent_name, temp in settings.get("temperatures", {}).items():
                if f"{agent_name}_temp" in self.model_selections:
                    self.model_selections[f"{agent_name}_temp"].setValue(temp)
        except FileNotFoundError:
            print("No saved settings found. Using defaults.")

    def get_current_settings(self):
        return {
            "companies": {agent_name: combo.currentText() for agent_name, combo in self.company_selections.items()},
            "models": {agent_name: combo.currentText() for agent_name, combo in self.model_selections.items() if not agent_name.endswith('_temp')},
            "temperatures": {agent_name: self.model_selections[f"{agent_name}_temp"].value() for agent_name in self.model_selections.keys() if not agent_name.endswith('_temp') and agent_name != "Embedding"},
        }

    def refresh_model_lists(self):
        for agent_name in self.company_selections.keys():
            if agent_name == "Embedding":
                self.update_embedding_model_list()
            else:
                self.update_model_list(agent_name)