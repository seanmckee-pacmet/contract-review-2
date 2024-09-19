from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QTextEdit, QFileDialog, QProgressBar,
                             QLabel)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from src.po_extract import process_multiple_purchase_orders
import json

class POExtractorTab(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        # Add a header
        header = QLabel("Purchase Order Extractor")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")
        layout.addWidget(header)

        # Add a description
        description = QLabel("Upload your purchase order files to extract referenced documents.")
        description.setStyleSheet("font-size: 14px; color: #cccccc; margin-bottom: 10px;")
        layout.addWidget(description)

        # Drag & Drop area
        self.upload_label = QLabel("Drag & Drop files here or click to select")
        self.upload_label.setAlignment(Qt.AlignCenter)
        self.upload_label.setStyleSheet("""
            border: 2px dashed #666666;
            border-radius: 5px;
            background-color: #2a2a2a;
            color: #cccccc;
            font-size: 16px;
            padding: 40px;
        """)
        self.upload_label.setAcceptDrops(True)
        self.upload_label.mousePressEvent = self.select_files
        layout.addWidget(self.upload_label)

        # Buttons and progress bar in a horizontal layout
        button_layout = QVBoxLayout()
        
        self.process_button = QPushButton('Process POs')
        self.process_button.clicked.connect(self.process_pos)
        self.process_button.setEnabled(False)
        self.process_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #555555;
            }
        """)
        button_layout.addWidget(self.process_button)

        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #444444;
                border-radius: 5px;
                text-align: center;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
            }
        """)
        button_layout.addWidget(self.progress_bar)

        layout.addLayout(button_layout)

        # Results area
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setStyleSheet("""
            QTextEdit {
                background-color: #2a2a2a;
                color: #ffffff;
                border: 1px solid #444444;
                font-family: Consolas, Monaco, monospace;
                font-size: 12px;
            }
        """)
        self.result_text.setMinimumHeight(300)  # Increase the minimum height
        layout.addWidget(self.result_text, 1)  # Give it a stretch factor of 1

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