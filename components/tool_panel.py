# components/tool_panel.py

import os
import json
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton, 
                             QInputDialog, QMessageBox, QMenu, QTextEdit, QDialog)
from PyQt6.QtCore import Qt, pyqtSignal

class ToolEditDialog(QDialog):
    def __init__(self, tool_name, script_content, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edit Tool: {tool_name}")
        self.setGeometry(100, 100, 600, 400)
        layout = QVBoxLayout(self)
        self.script_edit = QTextEdit()
        self.script_edit.setPlainText(script_content)
        layout.addWidget(self.script_edit)
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.accept)
        layout.addWidget(save_button)

    def get_script_content(self):
        return self.script_edit.toPlainText()

class ToolPanel(QWidget):
    tool_activated = pyqtSignal(str, str)  # Emits tool name and description
    tool_deactivated = pyqtSignal(str)  # Emits tool name

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.tools_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools")
        os.makedirs(self.tools_dir, exist_ok=True)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.tool_list = QListWidget()
        self.tool_list.itemClicked.connect(self.on_tool_clicked)
        self.tool_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tool_list.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.tool_list)

        button_layout = QHBoxLayout()
        self.add_button = QPushButton("Add Tool")
        self.add_button.clicked.connect(self.add_tool)
        button_layout.addWidget(self.add_button)

        self.activate_button = QPushButton("Activate")
        self.activate_button.clicked.connect(self.activate_tool)
        button_layout.addWidget(self.activate_button)

        self.deactivate_button = QPushButton("Deactivate")
        self.deactivate_button.clicked.connect(self.deactivate_tool)
        button_layout.addWidget(self.deactivate_button)

        layout.addLayout(button_layout)

        self.load_tools()

    def load_tools(self):
        self.tool_list.clear()
        for file in os.listdir(self.tools_dir):
            if file.endswith('.py'):
                self.tool_list.addItem(file[:-3])  # Remove .py extension

    def add_tool(self):
        name, ok = QInputDialog.getText(self, "Add Tool", "Enter tool name:")
        if ok and name:
            file_path = os.path.join(self.tools_dir, f"{name}.py")
            with open(file_path, 'w') as f:
                f.write(
                    f"# Tool: {name}\n"
                    "# Description: Add your tool description here\n\n"
                    "def activate():\n"
                    "    # Add your activation code here\n"
                    "    pass\n\n"
                    "def deactivate():\n"
                    "    # Add your deactivation code here\n"
                    "    pass\n\n"
                    "def execute(*args, **kwargs):\n"
                    "    # Add your main tool functionality here\n"
                    "    pass\n"
                )
            self.load_tools()

    def on_tool_clicked(self, item):
        tool_name = item.text()
        file_path = os.path.join(self.tools_dir, f"{tool_name}.py")
        with open(file_path, 'r') as f:
            content = f.read()
        dialog = ToolEditDialog(tool_name, content, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            with open(file_path, 'w') as f:
                f.write(dialog.get_script_content())

    def show_context_menu(self, position):
        item = self.tool_list.itemAt(position)
        if item:
            context_menu = QMenu(self)
            copy_action = context_menu.addAction("Copy")
            delete_action = context_menu.addAction("Delete")
            
            action = context_menu.exec(self.tool_list.mapToGlobal(position))
            if action == copy_action:
                self.copy_tool(item.text())
            elif action == delete_action:
                self.delete_tool(item.text())

    def copy_tool(self, tool_name):
        new_name, ok = QInputDialog.getText(self, "Copy Tool", "Enter new tool name:", text=f"Copy of {tool_name}")
        if ok and new_name:
            src_path = os.path.join(self.tools_dir, f"{tool_name}.py")
            dst_path = os.path.join(self.tools_dir, f"{new_name}.py")
            with open(src_path, 'r') as src, open(dst_path, 'w') as dst:
                content = src.read()
                dst.write(content.replace(f"Tool: {tool_name}", f"Tool: {new_name}"))
            self.load_tools()

    def delete_tool(self, tool_name):
        reply = QMessageBox.question(self, "Delete Tool", 
                                     f"Are you sure you want to delete the '{tool_name}' tool?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            os.remove(os.path.join(self.tools_dir, f"{tool_name}.py"))
            self.load_tools()

    def activate_tool(self):
        current_item = self.tool_list.currentItem()
        if current_item:
            tool_name = current_item.text()
            try:
                module = __import__(f"tools.{tool_name}", fromlist=['activate'])
                module.activate()
                description = self.get_tool_description(tool_name)
                self.tool_activated.emit(tool_name, description)
                QMessageBox.information(self, "Tool Activated", f"The tool '{tool_name}' has been activated.")
            except Exception as e:
                QMessageBox.warning(self, "Activation Error", f"Error activating tool: {str(e)}")

    def deactivate_tool(self):
        current_item = self.tool_list.currentItem()
        if current_item:
            tool_name = current_item.text()
            try:
                module = __import__(f"tools.{tool_name}", fromlist=['deactivate'])
                module.deactivate()
                self.tool_deactivated.emit(tool_name)
                QMessageBox.information(self, "Tool Deactivated", f"The tool '{tool_name}' has been deactivated.")
            except Exception as e:
                QMessageBox.warning(self, "Deactivation Error", f"Error deactivating tool: {str(e)}")

    def get_tool_description(self, tool_name):
        file_path = os.path.join(self.tools_dir, f"{tool_name}.py")
        with open(file_path, 'r') as f:
            content = f.read()
            for line in content.split('\n'):
                if line.startswith('# Description:'):
                    return line.split(':', 1)[1].strip()
        return "No description available"