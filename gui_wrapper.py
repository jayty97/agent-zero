import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QTextEdit, QLineEdit, QFileDialog, QLabel, QSplitter, QTabWidget, QScrollArea, 
                             QToolBar, QSizePolicy, QDoubleSpinBox, QMessageBox, QComboBox, QInputDialog, QListWidget, QListWidgetItem)
from PyQt6.QtGui import QIcon, QColor, QPalette, QTextCharFormat, QFont, QDragEnterEvent, QDropEvent
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QMimeData
from agent import Agent, AgentConfig
from python.helpers.print_style import PrintStyle
from python.helpers import files
import models
import traceback
import logging
import json
import shutil

# Set up logging
logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    def __init__(self, agent):
        super().__init__()
        self.agent = agent
        self.setWindowTitle("Agent Zero GUI")
        self.setGeometry(100, 100, 1200, 800)
        self.setup_ui()
        self.setup_styling()
        self.setAcceptDrops(True)
        self.current_mode = "Normal"

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Configurable prompt buttons at the top
        self.prompt_buttons_toolbar = PromptButtonsToolBar(self)
        main_layout.addWidget(self.prompt_buttons_toolbar)

        # Chat display
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        main_layout.addWidget(self.chat_display, 3)

        # Input area
        input_layout = QHBoxLayout()

        self.file_button = QPushButton("File")
        self.file_button.clicked.connect(self.open_file_dialog)
        input_layout.addWidget(self.file_button)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type a message...")
        self.input_field.returnPressed.connect(self.send_message)
        input_layout.addWidget(self.input_field, 4)

        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_message)
        input_layout.addWidget(self.send_button, 1)

        self.interrupt_button = QPushButton("Interrupt")
        self.interrupt_button.clicked.connect(self.interrupt_chat)
        input_layout.addWidget(self.interrupt_button, 1)

        main_layout.addLayout(input_layout)

        # Agent mode and spinner
        agent_mode_layout = QHBoxLayout()
        agent_mode_layout.addWidget(QLabel("Agent Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Normal", "BigBrain", "DreamTeam"])
        self.mode_combo.currentTextChanged.connect(self.on_agent_mode_changed)
        agent_mode_layout.addWidget(self.mode_combo)

        self.spinner_label = QLabel("Idle")
        agent_mode_layout.addWidget(self.spinner_label)
        agent_mode_layout.addStretch()

        main_layout.addLayout(agent_mode_layout)

        # Terminal view
        self.terminal_view = QTextEdit()
        self.terminal_view.setReadOnly(True)
        self.terminal_view.setStyleSheet("background-color: black; color: white;")
        main_layout.addWidget(self.terminal_view, 1)

        # Right panel (tabs for various features)
        right_panel = QTabWidget()
        right_panel.setMaximumWidth(400)

        self.file_manager = FileManagerPanel(self)
        right_panel.addTab(self.file_manager, "Files")

        self.memory_visualizer = MemoryVisualizerWidget(self)
        right_panel.addTab(self.memory_visualizer, "Memory")

        self.tool_panel = ToolPanel(self)
        right_panel.addTab(self.tool_panel, "Tools")

        self.settings_panel = SettingsPanel(self)
        right_panel.addTab(self.settings_panel, "Settings")

        # Main layout
        splitter = QSplitter(Qt.Orientation.Horizontal)
        left_widget = QWidget()
        left_widget.setLayout(main_layout)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)

        central_layout = QVBoxLayout(central_widget)
        central_layout.addWidget(splitter)

        self.spinner_timer = QTimer(self)
        self.spinner_timer.timeout.connect(self.update_spinner)
        self.spinner_chars = ['-', '\\', '|', '/']
        self.spinner_index = 0

    def setup_styling(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #2C3E50;
                color: #ECF0F1;
            }
            QPushButton {
                background-color: #3498DB;
                color: white;
                border: none;
                padding: 5px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #2980B9;
            }
            QLineEdit, QTextEdit {
                background-color: #34495E;
                color: #ECF0F1;
                border: 1px solid #7F8C8D;
                padding: 3px;
            }
            QTabWidget::pane {
                border: 1px solid #7F8C8D;
            }
            QTabBar::tab {
                background-color: #34495E;
                color: #ECF0F1;
                padding: 5px;
            }
            QTabBar::tab:selected {
                background-color: #2C3E50;
            }
        """)

    def send_message(self):
        message = self.input_field.text()
        if message:
            self.display_message("User", message)
            self.input_field.clear()
            self.process_message(message)

    def process_message(self, message):
        try:
            self.agent_thread = AgentThread(self.agent, message, self.current_mode)
            self.agent_thread.update_chat.connect(self.display_message)
            self.agent_thread.update_terminal.connect(self.update_terminal_view)
            self.agent_thread.start()
            self.start_spinner()
        except Exception as e:
            logger.error(f"Error in process_message: {str(e)}")
            logger.error(traceback.format_exc())
            self.display_message("System", f"An error occurred while processing the message: {str(e)}")

    def display_message(self, sender, message):
        cursor = self.chat_display.textCursor()
        format = QTextCharFormat()
        
        if sender == "User":
            format.setForeground(QColor("#3498DB"))
        elif sender == "Agent":
            format.setForeground(QColor("#2ECC71"))
        elif sender == "BigBrain":
            format.setForeground(QColor("#9B59B6"))
        elif sender.startswith("DreamTeam"):
            format.setForeground(QColor("#F1C40F"))
        else:
            format.setForeground(QColor("#E74C3C"))
        
        format.setFontWeight(QFont.Weight.Bold)
        cursor.insertText(f"{sender}: ", format)
        
        format.setFontWeight(QFont.Weight.Normal)
        cursor.insertText(f"{message}\n\n", format)
        
        self.chat_display.setTextCursor(cursor)
        self.chat_display.ensureCursorVisible()
        self.memory_visualizer.update_memory()

    def update_terminal_view(self, message):
        self.terminal_view.append(message)

    def on_agent_mode_changed(self, mode):
        self.current_mode = mode
        if mode == "BigBrain":
            self.input_field.setPlaceholderText("Ask BigBrain a complex question...")
        elif mode == "DreamTeam":
            self.input_field.setPlaceholderText("Pose a problem for the DreamTeam to solve...")
        else:
            self.input_field.setPlaceholderText("Type a message...")

    def interrupt_chat(self):
        if self.agent:
            self.agent.interrupt_chat()
            self.update_terminal_view("Chat interrupted by user.")
            self.stop_spinner()

    def start_spinner(self):
        self.spinner_timer.start(100)

    def stop_spinner(self):
        self.spinner_timer.stop()
        self.spinner_label.setText("Idle")

    def update_spinner(self):
        self.spinner_label.setText(f"Working {self.spinner_chars[self.spinner_index]}")
        self.spinner_index = (self.spinner_index + 1) % len(self.spinner_chars)

    def open_file_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File")
        if file_path:
            self.process_file(file_path)

    def process_file(self, file_path):
        file_name = os.path.basename(file_path)
        destination = os.path.join("work_dir", file_name)
        shutil.copy2(file_path, destination)
        self.file_manager.refresh_files()
        self.input_field.setText(f"[File added: {file_name}]")
        self.agent.append_message(f"User added file: {file_name}", human=True)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            self.process_file(file_path)

class AgentThread(QThread):
    update_chat = pyqtSignal(str, str)
    update_terminal = pyqtSignal(str)

    def __init__(self, agent, message, mode):
        super().__init__()
        self.agent = agent
        self.message = message
        self.mode = mode

    def run(self):
        try:
            self.update_terminal.emit(f"Agent 0 processing: {self.message}")
            if self.mode == "BigBrain":
                response = self.agent.process_bigbrain_request(self.message)
                self.update_chat.emit("Agent 0", response)
                self.update_terminal.emit("BigBrain request processed by Agent 0")
            elif self.mode == "DreamTeam":
                response = self.agent.process_dreamteam_request(self.message)
                self.update_chat.emit("Agent 0", response)
                self.update_terminal.emit("DreamTeam request processed by Agent 0")
            else:
                response = self.agent.message_loop(self.message)
                self.update_chat.emit("Agent 0", response)
                self.update_terminal.emit("Normal request processed by Agent 0")
        except Exception as e:
            error_msg = f"An error occurred: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
            logger.error(error_msg)
            self.update_chat.emit("System", error_msg)
            self.update_terminal.emit(f"Error occurred: {str(e)}")

class PromptButtonsToolBar(QToolBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.prompts = self.load_prompts()
        self.setup_ui()

    def setup_ui(self):
        for prompt_name, prompt_text in self.prompts.items():
            button = QPushButton(prompt_name)
            button.clicked.connect(lambda _, text=prompt_text: self.insert_prompt(text))
            self.addWidget(button)

            edit_button = QPushButton("!")
            edit_button.clicked.connect(lambda _, name=prompt_name: self.edit_prompt(name))
            self.addWidget(edit_button)

        add_button = QPushButton("+")
        add_button.clicked.connect(self.add_new_prompt)
        self.addWidget(add_button)

    def load_prompts(self):
        try:
            with open("prompts.json", "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def save_prompts(self):
        with open("prompts.json", "w") as f:
            json.dump(self.prompts, f)

    def insert_prompt(self, text):
        self.parent.input_field.setText(text)

    def edit_prompt(self, name):
        text, ok = QInputDialog.getMultiLineText(self, "Edit Prompt", "Enter new prompt text:", self.prompts[name])
        if ok:
            self.prompts[name] = text
            self.save_prompts()
            self.setup_ui()

    def add_new_prompt(self):
        name, ok = QInputDialog.getText(self, "New Prompt", "Enter prompt name:")
        if ok:
            text, ok = QInputDialog.getMultiLineText(self, "New Prompt", "Enter prompt text:")
            if ok:
                self.prompts[name] = text
                self.save_prompts()
                self.setup_ui()

class FileManagerPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.file_list = QListWidget()
        self.file_list.itemDoubleClicked.connect(self.file_action)
        layout.addWidget(self.file_list)

        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh_files)
        layout.addWidget(refresh_button)

    def refresh_files(self):
        self.file_list.clear()
        work_dir = files.get_abs_path("work_dir")
        for file_name in os.listdir(work_dir):
            if os.path.isfile(os.path.join(work_dir, file_name)):
                self.file_list.addItem(file_name)

    def file_action(self, item):
        file_name = item.text()
        action, ok = QInputDialog.getItem(self, "File Action", "Choose an action:", 
                                          ["Rename", "Delete", "Reference in chat"], 0, False)
        if ok:
            if action == "Rename":
                new_name, ok = QInputDialog.getText(self, "Rename File", "Enter new name:")
                if ok and new_name:
                    old_path = os.path.join("work_dir", file_name)
                    new_path = os.path.join("work_dir", new_name)
                    os.rename(old_path, new_path)
                    self.refresh_files()
            elif action == "Delete":
                reply = QMessageBox.question(self, "Delete File", 
                                             f"Are you sure you want to delete {file_name}?",
                                             QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    os.remove(os.path.join("work_dir", file_name))
                    self.refresh_files()
            elif action == "Reference in chat":
                self.parent.input_field.setText(f"[File reference: {file_name}]")

class MemoryVisualizerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.memory_text = QTextEdit()
        self.memory_text.setReadOnly(True)
        layout.addWidget(self.memory_text)

    def update_memory(self):
        if self.parent.agent:
            memory = self.parent.agent.get_memory_context()
            self.memory_text.setText(memory)

class ToolPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.tool_list = QTextEdit()
        self.tool_list.setReadOnly(True)
        self.tool_list.setText("Available tools will be listed here.")
        layout.addWidget(self.tool_list)

class SettingsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.chat_model_combo = QComboBox()
        self.chat_model_combo.addItems(["gpt-3.5-turbo", "gpt-4", "claude-3-sonnet-20240229"])
        layout.addWidget(QLabel("Chat Model:"))
        layout.addWidget(self.chat_model_combo)

        self.utility_model_combo = QComboBox()
        self.utility_model_combo.addItems(["gpt-3.5-turbo", "gpt-4", "claude-3-sonnet-20240229"])
        layout.addWidget(QLabel("Utility Model:"))
        layout.addWidget(self.utility_model_combo)

        self.embedding_model_combo = QComboBox()
        self.embedding_model_combo.addItems(["text-embedding-3-small", "text-embedding-3-large"])
        layout.addWidget(QLabel("Embedding Model:"))
        layout.addWidget(self.embedding_model_combo)

        self.save_button = QPushButton("Save Settings")
        self.save_button.clicked.connect(self.save_settings)
        layout.addWidget(self.save_button)

    def save_settings(self):
        # Implement settings saving logic here
        QMessageBox.information(self, "Settings Saved", "Settings have been saved successfully.")

def run_gui(agent):
    app = QApplication(sys.argv)
    window = MainWindow(agent)
    window.show()
    sys.exit(app.exec())