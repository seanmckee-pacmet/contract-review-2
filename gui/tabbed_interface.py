from PyQt5.QtWidgets import QTabWidget, QMainWindow, QApplication, QWidget, QVBoxLayout
from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QPalette, QColor
from .main_window import MainWindow
from .po_extractor import POExtractorTab
from .chat_window import ChatWindow

class StylishTabWidget(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDocumentMode(True)
        self.setTabPosition(QTabWidget.North)
        self.setMovable(True)
        self.setTabBarAutoHide(False)

class TabbedInterface(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Contract Review")
        self.setGeometry(100, 100, 1600, 900)

        # Set the base style
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #1e1e1e;
                color: #ffffff;
            }
        """)

        # Create a central widget and layout
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setCentralWidget(central_widget)

        # Create and style the tab widget
        self.tab_widget = StylishTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #3d3d3d;
                background-color: #2d2d2d;
                border-radius: 5px;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #b0b0b0;
                padding: 10px 15px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                margin-right: 2px;
            }
            QTabBar::tab:selected, QTabBar::tab:hover {
                background-color: #3d3d3d;
                color: #ffffff;
            }
            QTabBar::tab:selected {
                border-bottom: 2px solid #4CAF50;
            }
        """)

        layout.addWidget(self.tab_widget)
        
        # Add tabs
        self.tab_widget.addTab(MainWindow(), "Main")
        self.tab_widget.addTab(ChatWindow(), "Chat")
        self.tab_widget.addTab(POExtractorTab(), "PO Extractor")
        

    def sizeHint(self):
        return QSize(1600, 900)

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    
    # Set the application-wide palette
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(30, 30, 30))
    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Base, QColor(45, 45, 45))
    palette.setColor(QPalette.AlternateBase, QColor(60, 60, 60))
    palette.setColor(QPalette.ToolTipBase, Qt.white)
    palette.setColor(QPalette.ToolTipText, Qt.white)
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.Button, QColor(45, 45, 45))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Highlight, QColor(76, 175, 80))
    palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(palette)
    
    window = TabbedInterface()
    window.show()
    sys.exit(app.exec_())