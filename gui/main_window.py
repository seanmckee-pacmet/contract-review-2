import os
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QListWidget, QPushButton, QLabel, QSizePolicy,
                             QFileDialog, QLineEdit, QMessageBox, QListWidgetItem)
from PyQt5.QtCore import Qt, QMimeData
from PyQt5.QtGui import QDragEnterEvent, QDropEvent
from dotenv import load_dotenv
from llama_parse import LlamaParse
import openai
import qdrant_client
import json
from src.review import final_review as perform_final_review

# Load environment variables
load_dotenv()

# Set up LlamaParse
parser = LlamaParse(
    result_type="markdown",
    api_key=os.getenv("LLAMA_CLOUD_API_KEY"),
    model="gpt-4o-2024-08-06"
)

# Set up OpenAI client
openai_client = openai.Client(api_key=os.getenv("OPENAI_API_KEY"))

# Set up Qdrant client
qdrant_client = qdrant_client.QdrantClient(":memory:")
collection_name = "document-chunks"
embedding_model = "text-embedding-3-small"

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Document Review App")
        self.setGeometry(100, 100, 1000, 700)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        self.layout = QHBoxLayout(self.central_widget)
        
        # Left side: File drop area and current files
        left_layout = QVBoxLayout()
        self.drop_area = QLabel("Drop files here or click to upload")
        self.drop_area.setAlignment(Qt.AlignCenter)
        self.drop_area.setStyleSheet("border: 2px dashed #aaa")
        self.drop_area.setAcceptDrops(True)
        self.drop_area.dragEnterEvent = self.dragEnterEvent
        self.drop_area.dropEvent = self.dropEvent
        self.drop_area.mousePressEvent = self.open_file_dialog
        self.drop_area.setMinimumHeight(200)
        self.drop_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        self.current_files = QListWidget()
        
        left_layout.addWidget(self.drop_area)
        left_layout.addWidget(QLabel("Current Files:"))
        left_layout.addWidget(self.current_files)
        
        # Right side: Job list, company name input, and buttons
        right_layout = QVBoxLayout()
        self.job_list = QListWidget()
        
        self.company_name_input = QLineEdit()
        self.company_name_input.setPlaceholderText("Enter company name")
        
        self.add_job_button = QPushButton("Add Job")
        self.add_job_button.clicked.connect(self.add_job)
        self.review_button = QPushButton("Final Review")
        self.review_button.clicked.connect(self.final_review)
        
        right_layout.addWidget(QLabel("Jobs:"))
        right_layout.addWidget(self.job_list)
        right_layout.addWidget(QLabel("Company Name:"))
        right_layout.addWidget(self.company_name_input)
        right_layout.addWidget(self.add_job_button)
        right_layout.addWidget(self.review_button)
        
        self.layout.addLayout(left_layout, 2)
        self.layout.addLayout(right_layout, 1)
        
        self.files = []
        self.jobs = {}

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if os.path.isfile(file_path):
                self.add_file(file_path)
    
    def open_file_dialog(self, event):
        file_dialog = QFileDialog()
        file_paths, _ = file_dialog.getOpenFileNames(self, "Select Files")
        for file_path in file_paths:
            if os.path.isfile(file_path):
                self.add_file(file_path)

    def add_file(self, file_path):
        self.files.append(file_path)
        self.current_files.addItem(os.path.basename(file_path))

    def add_job(self):
        if self.current_files.count() > 0:
            company_name = self.company_name_input.text().strip()
            if not company_name:
                QMessageBox.warning(self, "Missing Company Name", "Please enter a company name before adding a job.")
                return
            
            file_count = self.current_files.count()
            
            if company_name in self.jobs:
                self.jobs[company_name] += file_count
            else:
                self.jobs[company_name] = file_count
            
            self.update_job_list()

            self.current_files.clear()
            self.files.clear()
            self.company_name_input.clear()
        else:
            QMessageBox.warning(self, "No Files", "Please add files before creating a job.")

    def update_job_list(self):
        self.job_list.clear()
        for company, file_count in self.jobs.items():
            self.job_list.addItem(f"Job: {company} ({file_count} files)")
    
    def final_review(self):
        print("Final review initiated")
        results = perform_final_review(self.jobs, self.files)
        self.display_results(results)

    def display_results(self, results):
        print("Search Results:")
        for clause_type, search_results in results.items():
            print(f"\nClause Type: {clause_type}")
            for result in search_results:
                print(f"  Score: {result.score}")
                print(f"  Company: {result.payload['company']}")
                print(f"  File: {result.payload['file']}")
                print(f"  Text: {result.payload['text'][:100]}...")  # Show first 100 characters