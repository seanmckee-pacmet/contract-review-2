import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton, QLabel, 
                             QSizePolicy, QFileDialog, QLineEdit, QMessageBox, QComboBox, QTextEdit,
                             QApplication, QMainWindow)
from PyQt5.QtCore import Qt, QMimeData, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QDragEnterEvent, QDropEvent, QColor, QFont, QPainter
from src.review import review_documents

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
        po_data = results['po_analysis']
        html_content = """
        <style>
            body {{ font-family: Arial, sans-serif; font-size: 13px; line-height: 1.6; color: #cccccc; background-color: #2a2a2a; }}
            h1 {{ color: #ffffff; border-bottom: 1px solid #444444; padding-bottom: 10px; }}
            h2 {{ color: #ffffff; margin-top: 20px; }}
            .section {{ margin-bottom: 20px; background-color: #333333; padding: 15px; border-radius: 4px; }}
            .subsection {{ margin-left: 20px; }}
            .clause {{ font-weight: bold; color: #4CAF50; }}
            .quote, .identifier, .requirement {{ margin-left: 20px; font-style: italic; color: #aaaaaa; }}
            .identifiers {{ margin-left: 40px; text-indent: -20px; }}
        </style>
        <h1>Contract Review Results for {company}</h1>
        """.format(company=results.get('company_name', 'Unknown Company'))

        # Purchase Order Analysis
        if results['po_analysis']:
            html_content += "<div class='section'><h2>Purchase Order Analysis</h2>"
            po_data = results['po_analysis']
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

if __name__ == "__main__":
    app = QApplication([])
    window = QMainWindow()
    main_widget = MainWindow()
    window.setCentralWidget(main_widget)
    window.setGeometry(100, 100, 1600, 900)
    window.setWindowTitle("Contract Review")
    window.show()
    app.exec_()