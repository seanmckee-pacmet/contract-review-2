from PyQt5.QtWidgets import QTabWidget, QWidget, QVBoxLayout
from PyQt5.QtCore import QSize
from gui.main_window import MainWindow
from gui.po_extractor import POExtractor

class NewView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        layout.addWidget(QWidget())  # Placeholder for the new view
        self.setLayout(layout)

class TabbedInterface(QTabWidget):
    def __init__(self):
        super().__init__()
        
        # Create instances of the views
        self.main_window = MainWindow()
        self.po_extractor = POExtractor()
        
        # Add tabs
        self.addTab(self.main_window, "Reviewer")
        self.addTab(self.po_extractor, "PO Extract")
        
        # Set the default tab to MainWindow
        self.setCurrentIndex(0)
        
        # Set a larger default size
        self.resize(1600, 900)  # Width: 1600px, Height: 900px