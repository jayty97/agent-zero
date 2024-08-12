# File: components/file_manager.py

import os
import shutil
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTreeView, QPushButton, QMenu, QMessageBox, 
                             QLabel, QSizePolicy, QFileDialog, QFrame)
from PyQt6.QtCore import Qt, QDir
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QPixmap

class FileManagerPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.work_dir = os.path.abspath(os.path.join(os.getcwd(), "work_dir"))
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # File preview area
        preview_frame = QFrame()
        preview_frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        preview_layout = QVBoxLayout(preview_frame)
        
        self.file_preview = QLabel("No file selected")
        self.file_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.file_preview.setMinimumHeight(150)
        self.file_preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        preview_layout.addWidget(self.file_preview)

        main_layout.addWidget(preview_frame)

        # File tree
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(['Name'])
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setColumnWidth(0, 250)
        self.tree.clicked.connect(self.on_file_clicked)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)

        main_layout.addWidget(self.tree)

        # Refresh button
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh_files)
        main_layout.addWidget(refresh_button)

        self.refresh_files()

    def refresh_files(self):
        self.model.clear()
        self.model.setHorizontalHeaderLabels(['Name'])
        self.populate_tree(self.work_dir, self.model.invisibleRootItem())

    def populate_tree(self, path, parent):
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            item_node = QStandardItem(item)
            item_node.setData(item_path, Qt.ItemDataRole.UserRole)
            parent.appendRow(item_node)
            if os.path.isdir(item_path):
                self.populate_tree(item_path, item_node)

    def on_file_clicked(self, index):
        item = self.model.itemFromIndex(index)
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if os.path.isfile(file_path):
            self.display_file_content(file_path)

    def display_file_content(self, file_path):
        _, file_extension = os.path.splitext(file_path)
        image_extensions = ['.png', '.jpg', '.jpeg', '.bmp', '.gif']

        if file_extension.lower() in image_extensions:
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                self.file_preview.setPixmap(pixmap.scaled(self.file_preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            else:
                self.file_preview.setText("Error loading image.")
        else:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(1000)  # Read first 1000 characters
            self.file_preview.setText(f"File: {os.path.basename(file_path)}\n\nPreview:\n{content}...")

    def show_context_menu(self, position):
        index = self.tree.indexAt(position)
        if not index.isValid():
            return

        item = self.model.itemFromIndex(index)
        file_path = item.data(Qt.ItemDataRole.UserRole)

        menu = QMenu()
        open_action = menu.addAction("Open")
        delete_action = menu.addAction("Delete")

        action = menu.exec(self.tree.viewport().mapToGlobal(position))
        if action == open_action:
            self.open_file(file_path)
        elif action == delete_action:
            self.delete_file(file_path)

    def open_file(self, file_path):
        try:
            QDir.setCurrent(os.path.dirname(file_path))
            QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error opening file: {str(e)}")

    def delete_file(self, file_path):
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
            self.refresh_files()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error deleting file/folder: {str(e)}")

    def add_file(self, file_path):
        destination = os.path.join(self.work_dir, os.path.basename(file_path))
        try:
            shutil.copy2(file_path, destination)
            self.refresh_files()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error copying file: {str(e)}")

    def set_work_dir(self, new_work_dir):
        self.work_dir = new_work_dir
        self.refresh_files()