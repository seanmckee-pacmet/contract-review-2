from PyQt5.QtWidgets import QTabWidget
from .main_window import MainWindow
from .po_extractor import POExtractorTab

class TabbedInterface(QTabWidget):
    def __init__(self):
        super().__init__()
        
        self.addTab(MainWindow(), "Main")
        self.addTab(POExtractorTab(), "PO Extractor")