from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtGui import QTextCursor, QColor, QTextCharFormat
from PyQt6.QtCore import Qt

class EnhancedChatDisplay(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.chat_history = []

    def append_message(self, sender, message):
        """
        Append a new message to the chat display.
        
        :param sender: The sender of the message (e.g., "User" or "Agent")
        :param message: The content of the message
        """
        self.chat_history.append({"role": sender.lower(), "content": message})
        
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        # Set format for sender
        sender_format = QTextCharFormat()
        sender_format.setFontWeight(700)  # Bold
        if sender.lower() == "user":
            sender_format.setForeground(QColor("#3498DB"))  # Blue for user
        else:
            sender_format.setForeground(QColor("#2ECC71"))  # Green for agent
        
        cursor.setCharFormat(sender_format)
        cursor.insertText(f"{sender}: ")
        
        # Reset format for message
        message_format = QTextCharFormat()
        message_format.setFontWeight(400)  # Normal weight
        message_format.setForeground(QColor("#ECF0F1"))  # Light color for message
        
        cursor.setCharFormat(message_format)
        cursor.insertText(f"{message}\n\n")
        
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def get_chat_history(self):
        """
        Get the current chat history.
        
        :return: A list of dictionaries containing chat messages
        """
        return self.chat_history

    def set_chat_history(self, history):
        """
        Set the chat history and update the display.
        
        :param history: A list of dictionaries containing chat messages
        """
        self.clear()
        self.chat_history = history
        for message in history:
            self.append_message(message['role'].capitalize(), message['content'])

    def clear(self):
        """
        Clear the chat display and history.
        """
        super().clear()
        self.chat_history = []