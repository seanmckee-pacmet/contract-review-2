from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QTextEdit, QFileDialog, QProgressBar,
                             QLabel)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from src.po_extract import process_multiple_purchase_orders
import json

class POProcessingThread(QThread):
    update_progress = pyqtSignal(int)
    finished = pyqtSignal(list)

    def __init__(self, file_paths):
        super().__init__()
        self.file_paths = file_paths

    def run(self):
        results = process_multiple_purchase_orders(self.file_paths)
        total_files = len(self.file_paths)
        for i, result in enumerate(results):
            self.update_progress.emit(int((i + 1) / total_files * 100))
        self.finished.emit(results)

class POExtractorTab(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        self.upload_label = QLabel("Drag & Drop files here or click to select")
        self.upload_label.setAlignment(Qt.AlignCenter)
        self.upload_label.setStyleSheet("""
            border: 2px dashed #666666;
            border-radius: 5px;
            background-color: #2a2a2a;
            color: #cccccc;
            font-size: 14px;
            padding: 20px;
        """)
        self.upload_label.setAcceptDrops(True)
        self.upload_label.mousePressEvent = self.select_files
        layout.addWidget(self.upload_label)

        self.process_button = QPushButton('Process POs')
        self.process_button.clicked.connect(self.process_pos)
        self.process_button.setEnabled(False)
        self.process_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #555555;
            }
        """)
        layout.addWidget(self.process_button)

        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #444444;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
            }
        """)
        layout.addWidget(self.progress_bar)

        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setStyleSheet("""
            QTextEdit {
                background-color: #2a2a2a;
                color: #ffffff;
                border: 1px solid #444444;
            }
        """)
        layout.addWidget(self.result_text)

        self.setLayout(layout)

        self.setAcceptDrops(True)
        self.file_paths = []

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        self.file_paths.extend(files)
        self.update_upload_label()

    def select_files(self, event):
        files, _ = QFileDialog.getOpenFileNames(self, "Select PO Files", "", "All Files (*);;PDF Files (*.pdf);;TIFF Files (*.tiff *.tif)")
        if files:
            self.file_paths.extend(files)
            self.update_upload_label()

    def update_upload_label(self):
        self.upload_label.setText(f"Selected {len(self.file_paths)} file(s)")
        self.process_button.setEnabled(True)

    def process_pos(self):
        self.process_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.result_text.clear()

        self.thread = POProcessingThread(self.file_paths)
        self.thread.update_progress.connect(self.update_progress)
        self.thread.finished.connect(self.on_processing_finished)
        self.thread.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def on_processing_finished(self, results):
        self.process_button.setEnabled(True)
        self.progress_bar.setValue(100)

        output = ""
        for result in results:
            output += f"File: {result['file_path']}\n"
            output += "Referenced Documents:\n"
            output += json.dumps(result['referenced_documents'], indent=2)
            output += "\n\n"

        self.result_text.setText(output)