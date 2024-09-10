from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, 
                             QTextEdit, QFileDialog)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QDragEnterEvent, QDropEvent

class POExtractor(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # File upload area
        self.upload_label = QLabel("Drag & Drop files here or click to select")
        self.upload_label.setAlignment(Qt.AlignCenter)
        self.upload_label.setStyleSheet("border: 2px dashed #aaa; padding: 20px;")
        self.upload_label.setAcceptDrops(True)
        self.upload_label.mousePressEvent = self.open_file_dialog

        # Extract button
        self.extract_button = QPushButton("Extract Docs")
        self.extract_button.clicked.connect(self.extract_docs)

        # Text view for displaying extracted content
        self.text_view = QTextEdit()
        self.text_view.setReadOnly(True)

        layout.addWidget(self.upload_label)
        layout.addWidget(self.extract_button)
        layout.addWidget(self.text_view)

        self.setLayout(layout)

        # Enable drag and drop
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        self.process_files(files)

    def open_file_dialog(self, event):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Files")
        if files:
            self.process_files(files)

    def process_files(self, files):
        file_names = [file.split('/')[-1] for file in files]
        self.upload_label.setText(f"Selected files: {', '.join(file_names)}")
        # Store the file paths for later use
        self.selected_files = files

    def extract_docs(self):
        if hasattr(self, 'selected_files'):
            # Here you would implement the actual extraction logic
            # For now, we'll just display the file names
            extracted_text = "Extracted content from:\n" + "\n".join(self.selected_files)
            self.text_view.setText(extracted_text)
        else:
            self.text_view.setText("No files selected for extraction.")