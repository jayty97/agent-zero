import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QListWidget, QTextEdit, QInputDialog, QMessageBox, QDialog)
from PyQt6.QtCore import Qt

class PromptEditDialog(QDialog):
    def __init__(self, prompt_content, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Prompt")
        self.setGeometry(100, 100, 600, 400)
        layout = QVBoxLayout(self)
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(prompt_content)
        layout.addWidget(self.text_edit)
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.accept)
        layout.addWidget(save_button)

    def get_edited_content(self):
        return self.text_edit.toPlainText()

class PromptManager(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.prompts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "prompts")
        self.setup_ui()
        self.load_prompts()

    def setup_ui(self):
        layout = QHBoxLayout(self)

        # Left side: List of prompts
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        self.prompt_list = QListWidget()
        self.prompt_list.itemClicked.connect(self.load_prompt_content)
        self.prompt_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.prompt_list.customContextMenuRequested.connect(self.show_context_menu)
        left_layout.addWidget(self.prompt_list)

        add_button = QPushButton("Add New Prompt")
        add_button.clicked.connect(self.add_new_prompt)
        left_layout.addWidget(add_button)

        layout.addWidget(left_widget)

        # Right side: Prompt content and edit buttons
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        self.prompt_content = QTextEdit()
        right_layout.addWidget(self.prompt_content)

        button_layout = QHBoxLayout()
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_prompt)
        button_layout.addWidget(save_button)

        delete_button = QPushButton("Delete")
        delete_button.clicked.connect(self.delete_prompt)
        button_layout.addWidget(delete_button)

        right_layout.addLayout(button_layout)
        layout.addWidget(right_widget)

    def load_prompts(self):
        self.prompt_list.clear()
        for file in os.listdir(self.prompts_dir):
            if file.endswith('.md'):
                self.prompt_list.addItem(file)

    def load_prompt_content(self, item):
        file_path = os.path.join(self.prompts_dir, item.text())
        with open(file_path, 'r') as f:
            self.prompt_content.setPlainText(f.read())

    def add_new_prompt(self):
        name, ok = QInputDialog.getText(self, "New Prompt", "Enter prompt file name (without .md):")
        if ok and name:
            file_name = f"{name}.md"
            file_path = os.path.join(self.prompts_dir, file_name)
            with open(file_path, 'w') as f:
                f.write("# New prompt\n\nEnter your prompt content here.")
            self.load_prompts()
            self.prompt_list.setCurrentRow(self.prompt_list.count() - 1)
            self.load_prompt_content(self.prompt_list.currentItem())

    def save_prompt(self):
        current_item = self.prompt_list.currentItem()
        if current_item:
            file_path = os.path.join(self.prompts_dir, current_item.text())
            with open(file_path, 'w') as f:
                f.write(self.prompt_content.toPlainText())
            QMessageBox.information(self, "Saved", "Prompt saved successfully.")
        else:
            QMessageBox.warning(self, "Error", "No prompt selected.")

    def delete_prompt(self):
        current_item = self.prompt_list.currentItem()
        if current_item:
            reply = QMessageBox.question(self, "Delete Prompt", 
                                         f"Are you sure you want to delete {current_item.text()}?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                file_path = os.path.join(self.prompts_dir, current_item.text())
                os.remove(file_path)
                self.load_prompts()
                self.prompt_content.clear()
        else:
            QMessageBox.warning(self, "Error", "No prompt selected.")

    def show_context_menu(self, position):
        item = self.prompt_list.itemAt(position)
        if item:
            dialog = PromptEditDialog(self.prompt_content.toPlainText(), self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                edited_content = dialog.get_edited_content()
                self.prompt_content.setPlainText(edited_content)
                self.save_prompt()