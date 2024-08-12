# components/prompt_buttons.py

from PyQt6.QtWidgets import QToolBar, QPushButton, QInputDialog, QMessageBox, QMenu
from PyQt6.QtCore import pyqtSignal, Qt

class PromptButtonsToolBar(QToolBar):
    insert_prompt_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.prompts = self.load_prompts()
        self.setup_ui()

    def setup_ui(self):
        self.clear()
        for prompt_name, prompt_text in self.prompts.items():
            button = QPushButton(prompt_name)
            button.clicked.connect(lambda _, text=prompt_text: self.insert_prompt(text))
            button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            button.customContextMenuRequested.connect(lambda pos, btn=button: self.show_button_context_menu(pos, btn))
            self.addWidget(button)

        add_button = QPushButton("+")
        add_button.clicked.connect(self.add_new_prompt)
        self.addWidget(add_button)

    def load_prompts(self):
        # Load prompts from a file or database
        # For now, we'll use a simple dictionary
        return {
            "Greeting": "Hello, how can I assist you today?",
            "Farewell": "Thank you for using our service. Have a great day!",
        }

    def insert_prompt(self, prompt_text):
        self.insert_prompt_signal.emit(prompt_text)

    def add_new_prompt(self):
        name, ok = QInputDialog.getText(self, "New Prompt", "Enter prompt name:")
        if ok and name:
            text, ok = QInputDialog.getMultiLineText(self, "New Prompt", "Enter prompt text:")
            if ok and text:
                self.prompts[name] = text
                self.setup_ui()

    def show_button_context_menu(self, pos, button):
        context_menu = QMenu(self)
        delete_action = context_menu.addAction("Delete")
        copy_action = context_menu.addAction("Copy")

        action = context_menu.exec(button.mapToGlobal(pos))

        if action == delete_action:
            self.delete_prompt(button.text())
        elif action == copy_action:
            self.copy_prompt(button.text())

    def delete_prompt(self, prompt_name):
        reply = QMessageBox.question(self, "Delete Prompt", 
                                     f"Are you sure you want to delete the '{prompt_name}' prompt?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            del self.prompts[prompt_name]
            self.setup_ui()

    def copy_prompt(self, prompt_name):
        new_name, ok = QInputDialog.getText(self, "Copy Prompt", "Enter new prompt name:", text=f"Copy of {prompt_name}")
        if ok and new_name:
            self.prompts[new_name] = self.prompts[prompt_name]
            self.setup_ui()

    def save_prompts(self):
        # Save prompts to a file or database
        pass