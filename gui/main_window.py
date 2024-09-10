import os
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QListWidget, QPushButton, QLabel, QSizePolicy,
                             QFileDialog, QLineEdit, QMessageBox, QListWidgetItem,
                             QTextEdit)
from PyQt5.QtCore import Qt, QMimeData
from PyQt5.QtGui import QDragEnterEvent, QDropEvent
from dotenv import load_dotenv
from src.review import review_documents
from PyQt5.QtGui import QFont
import json

# Load environment variables
load_dotenv()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Document Review App")
        self.setGeometry(100, 100, 1400, 800)  # Increased window width
        
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
        
        # Middle: Job list, company name input, and buttons
        middle_layout = QVBoxLayout()
        self.job_list = QListWidget()
        
        self.company_name_input = QLineEdit()
        self.company_name_input.setPlaceholderText("Enter company name")
        
        self.add_job_button = QPushButton("Add Job")
        self.add_job_button.clicked.connect(self.add_job)
        self.review_button = QPushButton("Review All Jobs")
        self.review_button.clicked.connect(self.review_all_jobs)
        
        middle_layout.addWidget(QLabel("Jobs:"))
        middle_layout.addWidget(self.job_list)
        middle_layout.addWidget(QLabel("Company Name:"))
        middle_layout.addWidget(self.company_name_input)
        middle_layout.addWidget(self.add_job_button)
        middle_layout.addWidget(self.review_button)
        
        # Right side: Results display
        right_layout = QVBoxLayout()
        self.results_display = ResultsDisplay()
        right_layout.addWidget(QLabel("Review Results:"))
        right_layout.addWidget(self.results_display)
        
        self.layout.addLayout(left_layout, 2)
        self.layout.addLayout(middle_layout, 1)
        self.layout.addLayout(right_layout, 3)  # Increased the stretch factor for the right layout
        
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
            
            self.jobs[company_name] = self.files.copy()
            
            self.update_job_list()

            self.current_files.clear()
            self.files.clear()
            self.company_name_input.clear()
        else:
            QMessageBox.warning(self, "No Files", "Please add files before creating a job.")

    def update_job_list(self):
        self.job_list.clear()
        for company, files in self.jobs.items():
            self.job_list.addItem(f"Job: {company} ({len(files)} files)")
    
    def review_all_jobs(self):
        self.results_display.clear()
        for company_name, file_paths in self.jobs.items():
            results = review_documents(file_paths, company_name)
            self.results_display.display_results(results)

from PyQt5.QtWidgets import QTextEdit, QVBoxLayout, QWidget

class ResultsDisplay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setFont(QFont("Arial", 11))
        self.layout.addWidget(self.text_edit)

    def clear(self):
        self.text_edit.clear()

    def display_results(self, results):
        self.text_edit.clear()
        html_content = """
        <style>
            body { font-family: Arial, sans-serif; font-size: 11px; line-height: 1.6; }
            h1 { color: #2c3e50; border-bottom: 2px solid #2c3e50; padding-bottom: 10px; }
            h2 { color: #34495e; margin-top: 20px; }
            .section { margin-bottom: 20px; }
            .subsection { margin-left: 20px; }
            .clause { font-weight: bold; color: #2980b9; }
            .quote, .identifier, .requirement { margin-left: 20px; font-style: italic; color: #555; }
            .identifiers { margin-left: 40px; text-indent: -20px; }
        </style>
        <h1>Contract Review Results</h1>
        """

        # Purchase Order Analysis
        if results['po_analysis']:
            html_content += "<div class='section'><h2>Purchase Order Analysis</h2>"
            po_data = json.loads(results['po_analysis'])
            html_content += "<div class='subsection'><h3 class='clause'>Clause Identifiers:</h3>"
            html_content += "<p class='identifiers'>"
            identifiers = po_data['clause_identifiers']
            html_content += ", ".join(f"<span class='identifier'>{identifier}</span>" for identifier in identifiers)
            html_content += "</p></div>"
            html_content += "<div class='subsection'><h3 class='clause'>Requirements:</h3><ul>"
            for req in po_data['requirements']:
                html_content += f"<li><span class='requirement'>{req}</span></li>"
            html_content += "</ul></div></div>"

        # Clause Analysis
        html_content += "<div class='section'><h2>Invoked Clauses</h2>"
        for clause in results['clause_analysis']:
            if clause['invoked'] == 'Yes':
                html_content += f"<div class='subsection'><p class='clause'>{clause['clause']}</p>"
                if clause['quotes']:
                    html_content += "<ul>"
                    for quote in clause['quotes']:
                        html_content += f"<li class='quote'><strong>{quote['clause']}:</strong> {quote['quote']}</li>"
                    html_content += "</ul>"
                html_content += "</div>"
        html_content += "</div>"

        self.text_edit.setHtml(html_content)
