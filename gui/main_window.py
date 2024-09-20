import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton, QLabel, 
                             QSizePolicy, QFileDialog, QLineEdit, QMessageBox, QComboBox, QTextEdit,
                             QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem, QMenu)
from PyQt5.QtCore import Qt, QMimeData, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QDragEnterEvent, QDropEvent, QColor, QFont, QPainter
from src.review import review_documents
import json

class DropArea(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                border: 1px dashed #aaaaaa;
                border-radius: 5px;
                background-color: #2a2a2a;
                color: #cccccc;
                font-size: 14px;
            }
        """)
        self.setAcceptDrops(True)
        self.setText("Drop files here or click to upload")

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if os.path.isfile(file_path):
                main_window = self.findMainWindow()
                if main_window:
                    main_window.add_file(file_path)
                else:
                    print("Error: Could not find MainWindow instance")

    def findMainWindow(self):
        parent = self.parent()
        while parent is not None:
            if isinstance(parent, MainWindow):
                return parent
            parent = parent.parent()
        return None

class ModernButton(QPushButton):
    def __init__(self, text, color):
        super().__init__(text)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                border: none;
                color: white;
                padding: 8px 16px;
                text-align: center;
                text-decoration: none;
                font-size: 13px;
                margin: 4px 2px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {QColor(color).darker(110).name()};
            }}
        """)

class LoadingIndicator(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.rotate)
        self.timer.start(50)
        self.setFixedSize(100, 100)
        self.hide()

    def rotate(self):
        self.angle = (self.angle + 10) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(50, 50)
        painter.rotate(self.angle)
        painter.setPen(Qt.NoPen)
        for i in range(8):
            painter.rotate(45)
            painter.setBrush(QColor(255, 255, 255, 25 * (i + 1)))
            painter.drawRect(-4, -20, 8, 20)

class ReviewThread(QThread):
    finished = pyqtSignal(dict)

    def __init__(self, jobs):
        super().__init__()
        self.jobs = jobs

    def run(self):
        results = {}
        for company_name, file_paths in self.jobs.items():
            results[company_name] = review_documents(file_paths, company_name)
        self.finished.emit(results)

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QLabel {
                font-size: 13px;
                color: #cccccc;
            }
            QListWidget, QTextEdit, QLineEdit, QComboBox {
                background-color: #2a2a2a;
                border: 1px solid #444444;
                border-radius: 4px;
                padding: 4px;
                font-size: 13px;
                color: #ffffff;
            }
            QListWidget::item {
                padding: 4px;
            }
            QListWidget::item:selected {
                background-color: #3a3a3a;
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
        
        self.layout = QHBoxLayout(self)
        
        # Left side: File drop area and current files
        left_layout = QVBoxLayout()
        self.drop_area = DropArea(self)
        self.drop_area.mousePressEvent = self.open_file_dialog
        self.drop_area.setMinimumHeight(150)
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
        
        self.add_job_button = ModernButton("Add Job", "#4CAF50")
        self.add_job_button.clicked.connect(self.add_job)
        self.review_button = ModernButton("Review All Jobs", "#2196F3")
        self.review_button.clicked.connect(self.review_all_jobs)
        
        self.job_selector = QComboBox()
        self.job_selector.currentIndexChanged.connect(self.update_results_display)
        middle_layout.addWidget(QLabel("Select Job:"))
        middle_layout.addWidget(self.job_selector)
        
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
        self.layout.addLayout(right_layout, 3)
        
        self.files = []
        self.jobs = {}
        self.review_results = {}

        # Add loading indicator
        self.loading_indicator = LoadingIndicator(self)
        self.loading_indicator.setGeometry(self.width() // 2 - 50, self.height() // 2 - 50, 100, 100)

        self.clear_button = ModernButton("Clear All", "#FF5722")
        self.clear_button.clicked.connect(self.clear_all)
        middle_layout.addWidget(self.clear_button)

        # Enable context menu for job_list and current_files
        self.job_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.job_list.customContextMenuRequested.connect(self.show_job_context_menu)
        
        self.current_files.setContextMenuPolicy(Qt.CustomContextMenu)
        self.current_files.customContextMenuRequested.connect(self.show_file_context_menu)
    
    def show_job_context_menu(self, position):
        menu = QMenu()
        delete_action = menu.addAction("Delete Job")
        action = menu.exec_(self.job_list.mapToGlobal(position))
        if action == delete_action:
            self.delete_selected_job()

    def show_file_context_menu(self, position):
        menu = QMenu()
        delete_action = menu.addAction("Delete File")
        action = menu.exec_(self.current_files.mapToGlobal(position))
        if action == delete_action:
            self.delete_selected_file()

    def delete_selected_job(self):
        current_item = self.job_list.currentItem()
        if current_item:
            company_name = current_item.text().split(" (")[0]
            del self.jobs[company_name]
            self.update_job_list()
            self.job_selector.clear()
            for company in self.jobs.keys():
                self.job_selector.addItem(company)

    def delete_selected_file(self):
        current_item = self.current_files.currentItem()
        if current_item:
            file_name = current_item.text()
            self.files = [f for f in self.files if os.path.basename(f) != file_name]
            self.current_files.takeItem(self.current_files.row(current_item))

    def clear_all(self):
        self.files.clear()
        self.jobs.clear()
        self.review_results.clear()
        self.current_files.clear()
        self.job_list.clear()
        self.job_selector.clear()
        self.company_name_input.clear()
        self.results_display.clear()

    def showEvent(self, event):
        super().showEvent(event)
        self.loading_indicator.setGeometry(self.width() // 2 - 50, self.height() // 2 - 50, 100, 100)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.loading_indicator.setGeometry(self.width() // 2 - 50, self.height() // 2 - 50, 100, 100)

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
            self.job_list.addItem(f"{company} ({len(files)} files)")
    
    def review_all_jobs(self):
        self.loading_indicator.show()
        self.setEnabled(False)  # Disable the entire window
        
        self.results_display.clear()
        self.review_results.clear()
        self.job_selector.clear()

        self.review_thread = ReviewThread(self.jobs)
        self.review_thread.finished.connect(self.on_review_finished)
        self.review_thread.start()

    def on_review_finished(self, results):
        self.review_results = results
        for company_name in results.keys():
            self.job_selector.addItem(company_name)

        if self.job_selector.count() > 0:
            self.job_selector.setCurrentIndex(0)
            self.update_results_display()

        self.loading_indicator.hide()
        self.setEnabled(True)  # Re-enable the window

    def update_results_display(self):
        selected_job = self.job_selector.currentText()
        if selected_job in self.review_results:
            self.results_display.display_results(self.review_results[selected_job])

import json
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtCore import Qt
import textwrap

class ResultsDisplay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Category / Clause / Quote"])
        self.tree.setColumnCount(1)
        self.tree.setWordWrap(True)
        self.tree.setUniformRowHeights(False)
        self.layout.addWidget(self.tree)
        
        with open('notable_clauses.json', 'r') as f:
            self.categories = json.load(f)

        self.setStyleSheet("""
            QTreeWidget {
                background-color: #2a2a2a;
                color: #cccccc;
                font-size: 13px;
            }
            QTreeWidget::item {
                padding: 4px;
            }
            QTreeWidget::item:selected {
                background-color: #3a3a3a;
            }
        """)

    def clear(self):
        self.tree.clear()

    def wrap_text(self, text, width=80):
        return '\n'.join(textwrap.wrap(text, width))

    def display_results(self, results):
        self.clear()
        po_data = results.get('po_analysis', {})
        company_name = results.get('company_name', 'Unknown Company')
        clause_analysis = results.get('clause_analysis', [])

        # Create root item
        root = QTreeWidgetItem(self.tree)
        root.setText(0, f"Contract Review Results for {company_name}")
        root.setFont(0, QFont("Arial", 12, QFont.Bold))
        root.setForeground(0, QColor("#ffffff"))

        # Add PO Analysis
        if po_data:
            po_item = QTreeWidgetItem(root)
            po_item.setText(0, "Purchase Order Analysis")
            po_item.setFont(0, QFont("Arial", 11, QFont.Bold))
import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton, QLabel, 
                             QSizePolicy, QFileDialog, QLineEdit, QMessageBox, QComboBox, QTextEdit,
                             QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem, QMenu)
from PyQt5.QtCore import Qt, QMimeData, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QDragEnterEvent, QDropEvent, QColor, QFont, QPainter
from src.review import review_documents
import json

class DropArea(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                border: 1px dashed #aaaaaa;
                border-radius: 5px;
                background-color: #2a2a2a;
                color: #cccccc;
                font-size: 14px;
            }
        """)
        self.setAcceptDrops(True)
        self.setText("Drop files here or click to upload")

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if os.path.isfile(file_path):
                main_window = self.findMainWindow()
                if main_window:
                    main_window.add_file(file_path)
                else:
                    print("Error: Could not find MainWindow instance")

    def findMainWindow(self):
        parent = self.parent()
        while parent is not None:
            if isinstance(parent, MainWindow):
                return parent
            parent = parent.parent()
        return None

class ModernButton(QPushButton):
    def __init__(self, text, color):
        super().__init__(text)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                border: none;
                color: white;
                padding: 8px 16px;
                text-align: center;
                text-decoration: none;
                font-size: 13px;
                margin: 4px 2px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {QColor(color).darker(110).name()};
            }}
        """)

class LoadingIndicator(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.rotate)
        self.timer.start(50)
        self.setFixedSize(100, 100)
        self.hide()

    def rotate(self):
        self.angle = (self.angle + 10) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(50, 50)
        painter.rotate(self.angle)
        painter.setPen(Qt.NoPen)
        for i in range(8):
            painter.rotate(45)
            painter.setBrush(QColor(255, 255, 255, 25 * (i + 1)))
            painter.drawRect(-4, -20, 8, 20)

class ReviewThread(QThread):
    finished = pyqtSignal(dict)

    def __init__(self, jobs):
        super().__init__()
        self.jobs = jobs

    def run(self):
        results = {}
        for company_name, file_paths in self.jobs.items():
            results[company_name] = review_documents(file_paths, company_name)
        self.finished.emit(results)

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QLabel {
                font-size: 13px;
                color: #cccccc;
            }
            QListWidget, QTextEdit, QLineEdit, QComboBox {
                background-color: #2a2a2a;
                border: 1px solid #444444;
                border-radius: 4px;
                padding: 4px;
                font-size: 13px;
                color: #ffffff;
            }
            QListWidget::item {
                padding: 4px;
            }
            QListWidget::item:selected {
                background-color: #3a3a3a;
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
        
        self.layout = QHBoxLayout(self)
        
        # Left side: File drop area and current files
        left_layout = QVBoxLayout()
        self.drop_area = DropArea(self)
        self.drop_area.mousePressEvent = self.open_file_dialog
        self.drop_area.setMinimumHeight(150)
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
        
        self.add_job_button = ModernButton("Add Job", "#4CAF50")
        self.add_job_button.clicked.connect(self.add_job)
        self.review_button = ModernButton("Review All Jobs", "#2196F3")
        self.review_button.clicked.connect(self.review_all_jobs)
        
        self.job_selector = QComboBox()
        self.job_selector.currentIndexChanged.connect(self.update_results_display)
        middle_layout.addWidget(QLabel("Select Job:"))
        middle_layout.addWidget(self.job_selector)
        
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
        self.layout.addLayout(right_layout, 3)
        
        self.files = []
        self.jobs = {}
        self.review_results = {}

        # Add loading indicator
        self.loading_indicator = LoadingIndicator(self)
        self.loading_indicator.setGeometry(self.width() // 2 - 50, self.height() // 2 - 50, 100, 100)

        self.clear_button = ModernButton("Clear All", "#FF5722")
        self.clear_button.clicked.connect(self.clear_all)
        middle_layout.addWidget(self.clear_button)

        # Enable context menu for job_list and current_files
        self.job_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.job_list.customContextMenuRequested.connect(self.show_job_context_menu)
        
        self.current_files.setContextMenuPolicy(Qt.CustomContextMenu)
        self.current_files.customContextMenuRequested.connect(self.show_file_context_menu)
    
    def show_job_context_menu(self, position):
        menu = QMenu()
        delete_action = menu.addAction("Delete Job")
        action = menu.exec_(self.job_list.mapToGlobal(position))
        if action == delete_action:
            self.delete_selected_job()

    def show_file_context_menu(self, position):
        menu = QMenu()
        delete_action = menu.addAction("Delete File")
        action = menu.exec_(self.current_files.mapToGlobal(position))
        if action == delete_action:
            self.delete_selected_file()

    def delete_selected_job(self):
        current_item = self.job_list.currentItem()
        if current_item:
            company_name = current_item.text().split(" (")[0]
            del self.jobs[company_name]
            self.update_job_list()
            self.job_selector.clear()
            for company in self.jobs.keys():
                self.job_selector.addItem(company)

    def delete_selected_file(self):
        current_item = self.current_files.currentItem()
        if current_item:
            file_name = current_item.text()
            self.files = [f for f in self.files if os.path.basename(f) != file_name]
            self.current_files.takeItem(self.current_files.row(current_item))

    def clear_all(self):
        self.files.clear()
        self.jobs.clear()
        self.review_results.clear()
        self.current_files.clear()
        self.job_list.clear()
        self.job_selector.clear()
        self.company_name_input.clear()
        self.results_display.clear()

    def showEvent(self, event):
        super().showEvent(event)
        self.loading_indicator.setGeometry(self.width() // 2 - 50, self.height() // 2 - 50, 100, 100)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.loading_indicator.setGeometry(self.width() // 2 - 50, self.height() // 2 - 50, 100, 100)

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
            self.job_list.addItem(f"{company} ({len(files)} files)")
    
    def review_all_jobs(self):
        self.loading_indicator.show()
        self.setEnabled(False)  # Disable the entire window
        
        self.results_display.clear()
        self.review_results.clear()
        self.job_selector.clear()

        self.review_thread = ReviewThread(self.jobs)
        self.review_thread.finished.connect(self.on_review_finished)
        self.review_thread.start()

    def on_review_finished(self, results):
        self.review_results = results
        for company_name in results.keys():
            self.job_selector.addItem(company_name)

        if self.job_selector.count() > 0:
            self.job_selector.setCurrentIndex(0)
            self.update_results_display()

        self.loading_indicator.hide()
        self.setEnabled(True)  # Re-enable the window

    def update_results_display(self):
        selected_job = self.job_selector.currentText()
        if selected_job in self.review_results:
            self.results_display.display_results(self.review_results[selected_job])

import json
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtCore import Qt
import textwrap

class ResultsDisplay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Category / Clause / Quote"])
        self.tree.setColumnCount(1)
        self.tree.setWordWrap(True)
        self.tree.setUniformRowHeights(False)
        self.layout.addWidget(self.tree)
        
        with open('notable_clauses.json', 'r') as f:
            self.categories = json.load(f)

        self.setStyleSheet("""
            QTreeWidget {
                background-color: #2a2a2a;
                color: #cccccc;
                font-size: 13px;
            }
            QTreeWidget::item {
                padding: 4px;
            }
            QTreeWidget::item:selected {
                background-color: #3a3a3a;
            }
        """)

    def clear(self):
        self.tree.clear()

    def wrap_text(self, text, width=80):
        return '\n'.join(textwrap.wrap(text, width))

    def display_results(self, results):
        self.clear()
        po_data = results.get('po_analysis', {})
        company_name = results.get('company_name', 'Unknown Company')
        clause_analysis = results.get('clause_analysis', [])

        # Create root item
        root = QTreeWidgetItem(self.tree)
        root.setText(0, f"Contract Review Results for {company_name}")
        root.setFont(0, QFont("Arial", 12, QFont.Bold))
        root.setForeground(0, QColor("#ffffff"))

        # Add PO Analysis
        if po_data:
            po_item = QTreeWidgetItem(root)
            po_item.setText(0, "Purchase Order Analysis")
            po_item.setFont(0, QFont("Arial", 11, QFont.Bold))
            po_item.setForeground(0, QColor("#4CAF50"))

            clause_identifiers = QTreeWidgetItem(po_item)
            clause_identifiers.setText(0, self.wrap_text(f"Clause Identifiers: {', '.join(po_data.get('clause_identifiers', []))}"))

            requirements_item = QTreeWidgetItem(po_item)
            requirements_item.setText(0, "Requirements")
            for req in po_data.get('requirements', []):
                req_item = QTreeWidgetItem(requirements_item)
                req_item.setText(0, self.wrap_text(req))

        # Process clause analysis
        for clause_id, _ in self.categories.items():
            matching_clause = next((clause for clause in clause_analysis if clause['clause'] == clause_id and clause['invoked'] == 'Yes'), None)
            
            if matching_clause:
                clause_item = QTreeWidgetItem(root)
                clause_item.setText(0, clause_id)
                clause_item.setFont(0, QFont("Arial", 10, QFont.Bold))
                clause_item.setForeground(0, QColor("#4CAF50"))
                
                for quote in matching_clause['quotes']:
                    quote_item = QTreeWidgetItem(clause_item)
                    
                    # Debugging: Print the entire quote dictionary
                    print(f"DEBUG: Quote object: {json.dumps(quote, indent=2)}")
                    
                    # Access the header directly from the quote
                    source = quote.get('header', 'Unknown Source')
                    doc_type = quote.get('document_type', 'Unknown Type')
                    
                    print(f"DEBUG: Extracted source: {source}, doc_type: {doc_type}")
                    
                    requires_review = quote.get('requires_human_review', 'Yes')
                    quote_text = f"[{source}] ({doc_type}) [Requires Review: {requires_review}]\n  {quote['quote']}"
                    full_text = self.wrap_text(quote_text)
                    
                    quote_item.setText(0, full_text)
                    
                    # Set the quote and document type to normal weight and light gray
                    quote_item.setData(0, Qt.UserRole, 0)
                    quote_item.setData(0, Qt.UserRole + 1, full_text)

        self.tree.expandToDepth(1)  # Expand to show categories and clauses, but not quotes

    def showEvent(self, event):
        super().showEvent(event)
        self.tree.itemExpanded.connect(self.adjust_column_width)
        self.tree.itemCollapsed.connect(self.adjust_column_width)

    def adjust_column_width(self, item):
        self.tree.resizeColumnToContents(0)

if __name__ == "__main__":
    app = QApplication([])
    window = QMainWindow()
    main_widget = MainWindow()
    window.setCentralWidget(main_widget)
    window.setGeometry(100, 100, 1600, 900)
    window.setWindowTitle("Contract Review")
    window.show()
    app.exec_()