from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit, 
                             QPushButton, QLabel, QFrame, QComboBox, QCompleter)
from PyQt5.QtCore import Qt, QTimer, QSortFilterProxyModel
from PyQt5.QtGui import QFont, QPalette, QColor, QStandardItemModel, QStandardItem
from src.qdrant_operations import initialize_qdrant, query_qdrant_for_clauses, get_ai_response

# Remove the SearchableComboBox class as it's no longer needed

class ChatWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.qdrant_client = initialize_qdrant("po_clauses", 1536)  # Uncomment and adjust as needed

    def init_ui(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                color: #ffffff;
                font-size: 14px;
            }
            QTextEdit, QLineEdit, QComboBox {
                background-color: #3b3b3b;
                border: 1px solid #555555;
                border-radius: 5px;
                padding: 5px;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: url(down_arrow.png);
                width: 14px;
                height: 14px;
            }
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Title
        title = QLabel("Chat with Documents")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)

        # Replace company selector with a QLineEdit
        company_layout = QHBoxLayout()
        company_label = QLabel("Enter Company Name:")
        self.company_input = QLineEdit()
        self.company_input.setPlaceholderText("Type company name here...")
        company_layout.addWidget(company_label)
        company_layout.addWidget(self.company_input)
        layout.addLayout(company_layout)

        # Chat history
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setFrameStyle(QFrame.NoFrame)
        self.chat_history.setMinimumHeight(300)
        layout.addWidget(self.chat_history)

        # Input area
        input_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type your message here...")
        self.input_field.returnPressed.connect(self.send_message)
        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_message)
        self.send_button.setCursor(Qt.PointingHandCursor)

        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_button)

        layout.addLayout(input_layout)

        self.setLayout(layout)

    def send_message(self):
        user_message = self.input_field.text()
        if not user_message.strip():
            return

        self.input_field.clear()
        
        company_name = self.company_input.text().strip()
        if not company_name:
            self.append_message('System', 'Please enter a company name.', '#FF0000')
            return
        
        # Use QTimer to add messages asynchronously
        QTimer.singleShot(0, lambda: self.append_message('You', user_message, '#4CAF50'))
        
        # Get AI response
        QTimer.singleShot(100, lambda: self.get_and_display_response(user_message, company_name))

    def append_message(self, sender, message, color):
        self.chat_history.append(f'<p style="color: {color};"><b>{sender}:</b> {message}</p>')

    def get_and_display_response(self, user_message, company):
        response = get_ai_response(self.qdrant_client, company, user_message)
        self.append_message('Assistant', response, '#2196F3')