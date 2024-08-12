# components/terminal_view.py

from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtCore import QObject, pyqtSignal

class TerminalView(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)

    def append_output(self, text):
        self.append(text)
        self.ensureCursorVisible()

class TerminalHandler(QObject):
    output_received = pyqtSignal(str)

    def write(self, text):
        self.output_received.emit(str(text))

    def flush(self):
        pass