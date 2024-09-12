from PyQt5.QtWidgets import QTabWidget, QMainWindow, QApplication
from PyQt5.QtCore import QSize
from .main_window import MainWindow
from .po_extractor import POExtractorTab

class TabbedInterface(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Document Review App")
        self.setGeometry(100, 100, 1600, 900)

        # Apply dark theme to the entire application
        self.setStyleSheet("""
            QMainWindow, QTabWidget, QWidget {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #ffffff;
                padding: 8px;
                border: 1px solid #3d3d3d;
            }
            QTabBar::tab:selected {
                background-color: #3d3d3d;
            }
            QTabWidget::pane {
                border: 1px solid #3d3d3d;
            }
        """)

        self.tab_widget = QTabWidget(self)
        self.setCentralWidget(self.tab_widget)
        
        self.tab_widget.addTab(MainWindow(), "Main")
        self.tab_widget.addTab(POExtractorTab(), "PO Extractor")

    def sizeHint(self):
        return QSize(1600, 900)

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    window = TabbedInterface()
    window.show()
    sys.exit(app.exec_())