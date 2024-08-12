from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QLabel

class MemoryVisualizerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.agent_wrapper = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.memory_label = QLabel("Agent Memory:")
        layout.addWidget(self.memory_label)
        
        self.memory_display = QTextEdit()
        self.memory_display.setReadOnly(True)
        layout.addWidget(self.memory_display)

    def set_agent(self, agent_wrapper):
        self.agent_wrapper = agent_wrapper
        self.update_memory()

    def update_memory(self):
        if self.agent_wrapper:
            memory = self.agent_wrapper.get_memory()
            self.memory_display.setPlainText(str(memory))
        else:
            self.memory_display.setPlainText("No agent assigned")

    def clear(self):
        self.memory_display.clear()