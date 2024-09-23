from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton, QLabel, 
                             QComboBox, QFileDialog, QMessageBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPalette, QColor
from src.qdrant_operations import initialize_qdrant, store_document_in_qdrant, get_company_documents, remove_document_from_qdrant

class DocumentManagerTab(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.qdrant_client = initialize_qdrant("company_documents", 1536)

    def initUI(self):
        # Set a dark background color for the entire tab
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor("#1e1e1e"))
        palette.setColor(QPalette.WindowText, Qt.white)
        self.setPalette(palette)

        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Company selection
        company_layout = QHBoxLayout()
        company_label = QLabel("Company:")
        company_label.setFont(QFont("Arial", 10))
        company_label.setStyleSheet("color: white;")
        self.company_select = QComboBox()
        self.company_select.setEditable(True)
        self.company_select.setFixedHeight(30)
        self.company_select.setFont(QFont("Arial", 10))
        self.company_select.setStyleSheet("""
            QComboBox {
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                padding: 2px 10px;
            }
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                color: white;
                selection-background-color: #3a3a3a;
            }
        """)
        company_layout.addWidget(company_label)
        company_layout.addWidget(self.company_select, 1)
        layout.addLayout(company_layout)

        # Document list
        doc_label = QLabel("Documents:")
        doc_label.setFont(QFont("Arial", 10))
        doc_label.setStyleSheet("color: white;")
        layout.addWidget(doc_label)
        self.document_list = QListWidget()
        self.document_list.setFont(QFont("Arial", 9))
        self.document_list.setStyleSheet("""
            QListWidget {
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 8px;
            }
            QListWidget::item:selected {
                background-color: #3a3a3a;
            }
        """)
        layout.addWidget(self.document_list)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        self.upload_button = QPushButton("Upload Document")
        self.remove_button = QPushButton("Remove Document")
        for button in (self.upload_button, self.remove_button):
            button.setFixedHeight(35)
            button.setFont(QFont("Arial", 10))
            button.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 5px 15px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
        self.upload_button.clicked.connect(self.upload_document)
        self.remove_button.clicked.connect(self.remove_document)
        button_layout.addWidget(self.upload_button)
        button_layout.addWidget(self.remove_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

        # Connect signals
        self.company_select.currentTextChanged.connect(self.update_document_list)

    def upload_document(self):
        company = self.company_select.currentText()
        if not company:
            QMessageBox.warning(self, "Error", "Please enter a company name.")
            return

        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(self, "Select Document")
        if file_path:
            store_document_in_qdrant(self.qdrant_client, company, file_path)
            self.update_document_list()

    def remove_document(self):
        company = self.company_select.currentText()
        selected_items = self.document_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Error", "Please select a document to remove.")
            return

        document_name = selected_items[0].text()
        remove_document_from_qdrant(self.qdrant_client, company, document_name)
        self.update_document_list()

    def update_document_list(self):
        company = self.company_select.currentText()
        self.document_list.clear()
        if company:
            documents = get_company_documents(self.qdrant_client, company)
            self.document_list.addItems(documents)