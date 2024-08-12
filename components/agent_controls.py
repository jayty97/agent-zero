from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt6.QtCore import pyqtSignal

class AgentControlsWidget(QWidget):
    agent_changed = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.agent = None
        self.setup_ui()

    def setup_ui(self):
        """
        Set up the user interface for the agent controls.
        """
        layout = QHBoxLayout(self)
        self.status_label = QLabel("Status: No agent selected")
        layout.addWidget(self.status_label)

    def set_agent(self, agent):
        """
        Set the current agent and update the status label.
        
        :param agent: The agent object to be set
        """
        self.agent = agent
        self.status_label.setText(f"Status: Agent active")
        self.agent_changed.emit(agent)

    def get_current_agent(self):
        """
        Get the current agent object.
        
        :return: The current agent object
        """
        return self.agent