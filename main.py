import sys
from PyQt5.QtWidgets import QApplication
from gui.tabbed_interface import TabbedInterface

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TabbedInterface()
    window.show()
    sys.exit(app.exec_())
