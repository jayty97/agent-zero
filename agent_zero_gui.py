import sys
import os
import logging
import traceback
import json
from typing import Dict, Any, List
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QSplitter, QTabWidget, QPushButton, QLineEdit, 
    QLabel, QFileDialog, QMenuBar, QStatusBar, QMessageBox, QDialog, QInputDialog,
    QScrollArea, QStyleFactory, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QObject, pyqtSignal, QUrl, QThreadPool, QRunnable
from PyQt6.QtGui import QAction, QDesktopServices, QPalette, QColor, QFont

from components.chat_display import EnhancedChatDisplay
from components.agent_controls import AgentControlsWidget
from components.prompt_buttons import PromptButtonsToolBar
from components.tool_panel import ToolPanel
from components.file_manager import FileManagerPanel
from components.settings_panel import SettingsPanel
from components.terminal_view import TerminalView, TerminalHandler
from components.prompt_manager import PromptManager

from agent_wrapper import AgentWrapper

logging.basicConfig(filename='agent_zero.log', level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)

class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as e:
            logger.error(f"Error in worker thread: {str(e)}")
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()

class AgentZeroGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Agent Zero Interface")
        self.setGeometry(100, 100, 1200, 800)
        self.current_project = None
        self.agent_wrapper = None
        self.threadpool = QThreadPool()
        self.setup_ui()
        self.apply_styles()

    def setup_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        main_layout = QVBoxLayout(self.central_widget)

        self.create_menu_bar()

        self.prompt_buttons = PromptButtonsToolBar(self)
        self.addToolBar(self.prompt_buttons)

        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel: Chat display and input
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # Chat display
        self.chat_display = EnhancedChatDisplay()
        self.chat_display.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        left_layout.addWidget(self.chat_display)

        # Input widget
        input_widget = QWidget()
        input_layout = QVBoxLayout(input_widget)
        
        # Message input and send button
        message_widget = QWidget()
        message_layout = QHBoxLayout(message_widget)
        self.message_input = QLineEdit()
        self.message_input.returnPressed.connect(self.send_message)
        message_layout.addWidget(self.message_input)

        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_message)
        message_layout.addWidget(self.send_button)
        
        input_layout.addWidget(message_widget)

        # Context size label
        self.context_size_label = QLabel("Context Size: 0 tokens")
        input_layout.addWidget(self.context_size_label)

        # Control buttons
        control_widget = QWidget()
        control_layout = QHBoxLayout(control_widget)
        self.file_upload_button = QPushButton("Upload File")
        self.file_upload_button.clicked.connect(self.upload_file)
        control_layout.addWidget(self.file_upload_button)

        self.agent_controls = AgentControlsWidget(self)
        control_layout.addWidget(self.agent_controls)

        self.interrupt_button = QPushButton("Interrupt")
        self.interrupt_button.clicked.connect(self.interrupt_agent)
        control_layout.addWidget(self.interrupt_button)

        self.bigbrain_button = QPushButton("Call BigBrain")
        self.bigbrain_button.clicked.connect(self.call_bigbrain)
        control_layout.addWidget(self.bigbrain_button)

        self.dreamteam_button = QPushButton("Call DreamTeam")
        self.dreamteam_button.clicked.connect(self.call_dreamteam)
        control_layout.addWidget(self.dreamteam_button)

        input_layout.addWidget(control_widget)

        left_layout.addWidget(input_widget)

        main_splitter.addWidget(left_widget)

        # Right panel: Tabbed interface
        self.tab_widget = QTabWidget()

        # Wrap each tab content in a QScrollArea for better scalability
        self.file_manager = FileManagerPanel(self)
        scroll_file_manager = QScrollArea()
        scroll_file_manager.setWidget(self.file_manager)
        scroll_file_manager.setWidgetResizable(True)
        self.tab_widget.addTab(scroll_file_manager, "Files")

        self.tool_panel = ToolPanel(self)
        self.tool_panel.tool_activated.connect(self.on_tool_activated)
        self.tool_panel.tool_deactivated.connect(self.on_tool_deactivated)
        scroll_tool = QScrollArea()
        scroll_tool.setWidget(self.tool_panel)
        scroll_tool.setWidgetResizable(True)
        self.tab_widget.addTab(scroll_tool, "Tools")

        self.settings_panel = SettingsPanel(self)
        scroll_settings = QScrollArea()
        scroll_settings.setWidget(self.settings_panel)
        scroll_settings.setWidgetResizable(True)
        self.tab_widget.addTab(scroll_settings, "Settings")
        self.settings_panel.settings_changed.connect(self.setup_agent)

        self.prompt_manager = PromptManager(self)
        scroll_prompt = QScrollArea()
        scroll_prompt.setWidget(self.prompt_manager)
        scroll_prompt.setWidgetResizable(True)
        self.tab_widget.addTab(scroll_prompt, "Prompts")

        main_splitter.addWidget(self.tab_widget)
        main_splitter.setSizes([2*self.width()//3, self.width()//3])

        main_layout.addWidget(main_splitter)

        self.terminal_view = TerminalView(self)
        self.terminal_view.setFixedHeight(100)
        main_layout.addWidget(self.terminal_view)

        self.terminal_handler = TerminalHandler()
        self.terminal_handler.output_received.connect(self.terminal_view.append_output)

        sys.stdout = self.terminal_handler
        sys.stderr = self.terminal_handler

        self.statusBar().showMessage("Ready")

        self.prompt_buttons.insert_prompt_signal.connect(self.insert_prompt_to_input)

        # Initialize agent
        self.setup_agent()

    def apply_styles(self):
        self.setStyle(QStyleFactory.create("Fusion"))
        
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        dark_palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
        dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
        dark_palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
        dark_palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
        dark_palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
        dark_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        dark_palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
        
        self.setPalette(dark_palette)
        
        self.setStyleSheet("""
            QToolTip { color: #ffffff; background-color: #2a82da; border: 1px solid white; }
            QWidget { background-color: #353535; color: #ffffff; }
            QTextEdit { background-color: #252525; color: #ffffff; }
            QPlainTextEdit { background-color: #252525; color: #ffffff; }
            QLineEdit { background-color: #252525; color: #ffffff; }
            QPushButton { background-color: #2a82da; color: #ffffff; }
            QPushButton:hover { background-color: #3d8fe0; }
            QTabWidget::pane { border: 1px solid #444444; }
            QTabBar::tab { background-color: #353535; color: #ffffff; padding: 5px; }
            QTabBar::tab:selected { background-color: #2a82da; }
            QScrollBar:vertical { border: none; background: #353535; width: 10px; margin: 0px 0px 0px 0px; }
            QScrollBar::handle:vertical { background: #2a82da; min-height: 20px; }
            QScrollBar::add-line:vertical { border: none; background: none; }
            QScrollBar::sub-line:vertical { border: none; background: none; }
        """)
        
        font = QFont("Segoe UI", 10)
        QApplication.setFont(font)

    def create_menu_bar(self):
        menubar = self.menuBar()
        
        file_menu = menubar.addMenu("File")
        file_menu.addAction("Save Session", self.save_session)
        file_menu.addAction("Load Session", self.load_session)
        file_menu.addAction("Print Chat History", self.print_chat_history)
        file_menu.addAction("Import Files", self.import_files)
        
        edit_menu = menubar.addMenu("Edit")
        edit_menu.addAction("Copy", self.copy_selected_text)
        edit_menu.addAction("Paste", self.paste_to_input)
        edit_menu.addAction("Interrupt Agent", self.interrupt_agent)
        
        project_menu = menubar.addMenu("Project")
        project_menu.addAction("New Project", self.new_project)
        project_menu.addAction("Open Project", self.open_project)
        project_menu.addAction("Save Project", self.save_project)
        project_menu.addAction("Close Project", self.close_project)
        
        help_menu = menubar.addMenu("Help")
        help_menu.addAction("View README", self.view_readme)
        help_menu.addAction("Join Discord", self.join_discord)

    def setup_agent(self):
        try:
            settings = self.settings_panel.get_current_settings()
            self.agent_wrapper = AgentWrapper(settings)
            self.agent_wrapper.agent_output.connect(self.terminal_view.append_output)
            self.agent_controls.set_agent(self.agent_wrapper)
            self.statusBar().showMessage("Agent setup complete")
        except Exception as e:
            logger.error(f"Error setting up agent: {str(e)}")
            self.show_error_message("Agent Setup Error", f"Error setting up agent: {str(e)}\nPlease check your model settings and ensure all required API keys are set.")

    def send_message(self):
        message = self.message_input.text()
        if message and self.agent_wrapper:
            self.chat_display.append_message("User", message)
            self.message_input.clear()
            
            worker = Worker(self.agent_wrapper.message_loop, message)
            worker.signals.result.connect(self.handle_agent_response)
            worker.signals.error.connect(self.handle_agent_error)
            
            self.threadpool.start(worker)
            self.statusBar().showMessage("Processing message...")
        elif not self.agent_wrapper:
            self.show_error_message("No Agent", "Please set up the agent in the Settings tab before sending messages.")

    def handle_agent_response(self, response):
        self.chat_display.append_message("Agent", response)
        self.context_size_label.setText(f"Context Size: {self.agent_wrapper.get_context_size()} tokens")
        self.statusBar().showMessage("Message processed")

    def handle_agent_error(self, error_info):
        exctype, value, tb = error_info
        error_msg = ''.join(traceback.format_exception(exctype, value, tb))
        logger.error(f"Error processing message: {error_msg}")
        self.show_error_message("Message Processing Error", f"Error processing message: {str(value)}")
        self.statusBar().showMessage("Error processing message")

    def call_bigbrain(self):
        message = self.message_input.text()
        if message and self.agent_wrapper:
            self.chat_display.append_message("User", f"[BigBrain] {message}")
            self.message_input.clear()
            
            worker = Worker(self.agent_wrapper.call_bigbrain, message)
            worker.signals.result.connect(self.handle_agent_response)
            worker.signals.error.connect(self.handle_agent_error)
            
            self.threadpool.start(worker)
            self.statusBar().showMessage("Processing BigBrain request...")
        elif not self.agent_wrapper:
            self.show_error_message("No Agent", "Please set up the agent in the Settings tab before using BigBrain.")

    def call_dreamteam(self):
        message = self.message_input.text()
        if message and self.agent_wrapper:
            self.chat_display.append_message("User", f"[DreamTeam] {message}")
            self.message_input.clear()
            
            worker = Worker(self.agent_wrapper.call_dreamteam, message)
            worker.signals.result.connect(self.handle_agent_response)
            worker.signals.error.connect(self.handle_agent_error)
            
            self.threadpool.start(worker)
            self.statusBar().showMessage("Processing DreamTeam request...")
        elif not self.agent_wrapper:
            self.show_error_message("No Agent", "Please set up the agent in the Settings tab before using DreamTeam.")

    def insert_prompt_to_input(self, prompt_text):
        cursor = self.message_input.cursorPosition()
        current_text = self.message_input.text()
        new_text = current_text[:cursor] + prompt_text + current_text[cursor:]
        self.message_input.setText(new_text)
        self.message_input.setCursorPosition(cursor + len(prompt_text))

    def upload_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Upload File")
        if file_name:
            try:
                logger.info(f"File uploaded: {file_name}")
                self.file_manager.add_file(file_name)
            except Exception as e:
                logger.error(f"Error uploading file: {str(e)}")
                self.show_error_message("File Upload Error", f"Error uploading file: {str(e)}")

    def interrupt_agent(self):
        if self.agent_wrapper:
            try:
                self.agent_wrapper.main_agent.interrupt_message = "Agent interrupted by user."
                logger.info("Agent interrupted")
                print("Agent interrupted")
            except Exception as e:
                logger.error(f"Error interrupting agent: {str(e)}")
                self.show_error_message("Interrupt Error", f"Error interrupting agent: {str(e)}")
        else:
            self.show_error_message("No Agent", "No agent is currently set up to interrupt.")

    def on_tool_activated(self, tool_name, description):
        if self.agent_wrapper:
            self.agent_wrapper.activate_tool(tool_name, description)

    def on_tool_deactivated(self, tool_name):
        if self.agent_wrapper:
            self.agent_wrapper.deactivate_tool(tool_name)

    def new_project(self):
        project_name, ok = QInputDialog.getText(self, "New Project", "Enter project name:")
        if ok and project_name:
            self.current_project = project_name
            project_dir = os.path.join("projects", project_name)
            os.makedirs(project_dir, exist_ok=True)
            self.file_manager.set_work_dir(project_dir)
            if self.agent_wrapper:
                self.agent_wrapper.set_work_dir(project_dir)
            self.statusBar().showMessage(f"Created new project: {project_name}")

    def open_project(self):
        project_dir = QFileDialog.getExistingDirectory(self, "Open Project", "projects")
        if project_dir:
            try:
                self.current_project = os.path.basename(project_dir)
                self.file_manager.set_work_dir(project_dir)
                if self.agent_wrapper:
                    self.agent_wrapper.set_work_dir(project_dir)
                self.load_project_data()
                self.statusBar().showMessage(f"Opened project: {self.current_project}")
            except Exception as e:
                logger.error(f"Error opening project: {str(e)}")
                self.show_error_message("Project Open Error", f"Error opening project: {str(e)}")

    def save_project(self):
        if not self.current_project:
            QMessageBox.warning(self, "No Project", "No project is currently open.")
            return
        
        project_dir = os.path.join("projects", self.current_project)
        os.makedirs(project_dir, exist_ok=True)
        
        try:
            chat_history = self.chat_display.get_chat_history()
            with open(os.path.join(project_dir, "chat_history.json"), "w") as f:
                json.dump(chat_history, f)
            
            if self.agent_wrapper:
                agent_memory = self.agent_wrapper.get_memory()
                with open(os.path.join(project_dir, "agent_memory.json"), "w") as f:
                    json.dump(agent_memory, f)
            
            self.statusBar().showMessage(f"Saved project: {self.current_project}")
        except Exception as e:
            logger.error(f"Error saving project: {str(e)}")
            self.show_error_message("Project Save Error", f"Error saving project: {str(e)}")

    def close_project(self):
        if not self.current_project:
            QMessageBox.warning(self, "No Project", "No project is currently open.")
            return
        
        reply = QMessageBox.question(self, "Close Project", 
                                     "Do you want to save the current project before closing?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)
        
        if reply == QMessageBox.StandardButton.Cancel:
            return
        elif reply == QMessageBox.StandardButton.Yes:
            self.save_project()
        
        self.current_project = None
        work_dir = os.path.join(os.getcwd(), "work_dir")
        self.file_manager.set_work_dir(work_dir)
        if self.agent_wrapper:
            self.agent_wrapper.set_work_dir(work_dir)
        self.chat_display.clear()
        self.statusBar().showMessage("Project closed")

    def load_project_data(self):
        project_dir = os.path.join("projects", self.current_project)
        
        try:
            chat_history_path = os.path.join(project_dir, "chat_history.json")
            if os.path.exists(chat_history_path):
                with open(chat_history_path, "r") as f:
                    chat_history = json.load(f)
                self.chat_display.set_chat_history(chat_history)
            
            memory_path = os.path.join(project_dir, "agent_memory.json")
            if os.path.exists(memory_path) and self.agent_wrapper:
                with open(memory_path, "r") as f:
                    agent_memory = json.load(f)
                self.agent_wrapper.set_memory(agent_memory)
            
        except Exception as e:
            logger.error(f"Error loading project data: {str(e)}")
            self.show_error_message("Project Load Error", f"Error loading project data: {str(e)}")

    def view_readme(self):
        try:
            readme_path = os.path.join(os.getcwd(), "README.md")
            if os.path.exists(readme_path):
                with open(readme_path, 'r') as file:
                    content = file.read()
                    self.show_readme_dialog(content)
            else:
                raise FileNotFoundError("README.md not found in the root directory.")
        except Exception as e:
            logger.error(f"Error opening README: {str(e)}")
            self.show_error_message("README Error", f"Error opening README: {str(e)}")

    def show_readme_dialog(self, content):
        dialog = QDialog(self)
        dialog.setWindowTitle("README")
        layout = QVBoxLayout(dialog)
        text_edit = QTextEdit()
        text_edit.setPlainText(content)
        text_edit.setReadOnly(True)
        layout.addWidget(text_edit)
        dialog.exec()

    def join_discord(self):
        QDesktopServices.openUrl(QUrl("https://discord.gg/B8KZKNsPpj"))

    def save_session(self):
        file_name, _ = QFileDialog.getSaveFileName(self, "Save Session", "", "JSON Files (*.json)")
        if file_name:
            try:
                session_data = {
                    "chat_history": self.chat_display.get_chat_history(),
                    "agent_memory": self.agent_wrapper.get_memory() if self.agent_wrapper else None,
                }
                with open(file_name, 'w') as f:
                    json.dump(session_data, f)
                self.statusBar().showMessage(f"Session saved to {file_name}")
            except Exception as e:
                logger.error(f"Error saving session: {str(e)}")
                self.show_error_message("Save Session Error", f"Error saving session: {str(e)}")

    def load_session(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Load Session", "", "JSON Files (*.json)")
        if file_name:
            try:
                with open(file_name, 'r') as f:
                    session_data = json.load(f)
                self.chat_display.set_chat_history(session_data["chat_history"])
                if self.agent_wrapper and session_data["agent_memory"]:
                    self.agent_wrapper.set_memory(session_data["agent_memory"])
                self.statusBar().showMessage(f"Session loaded from {file_name}")
            except Exception as e:
                logger.error(f"Error loading session: {str(e)}")
                self.show_error_message("Load Session Error", f"Error loading session: {str(e)}")

    def print_chat_history(self):
        history = self.chat_display.get_chat_history()
        print("Chat History:")
        for message in history:
            print(f"{message['role']}: {message['content']}")

    def import_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Import Files")
        for file in files:
            try:
                self.file_manager.add_file(file)
            except Exception as e:
                logger.error(f"Error importing file {file}: {str(e)}")
                self.show_error_message("File Import Error", f"Error importing file {file}: {str(e)}")

    def copy_selected_text(self):
        self.chat_display.copy()

    def paste_to_input(self):
        clipboard = QApplication.clipboard()
        self.message_input.insert(clipboard.text())

    def show_error_message(self, title, message):
        QMessageBox.critical(self, title, message)

    def closeEvent(self, event):
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        super().closeEvent(event)

if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        main_window = AgentZeroGUI()
        main_window.show()
        sys.exit(app.exec())
    except Exception as e:
        error_msg = f"Critical error: {''.join(traceback.format_exception(type(e), e, e.__traceback__))}"
        logger.critical(error_msg)
        print(error_msg)
        
        error_box = QMessageBox()
        error_box.setIcon(QMessageBox.Icon.Critical)
        error_box.setText("A critical error has occurred during startup.")
        error_box.setInformativeText("The application cannot continue. Please check the log file for details.")
        error_box.setDetailedText(error_msg)
        error_box.setWindowTitle("Critical Startup Error")
        error_box.exec()
        
        sys.exit(1)