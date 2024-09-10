import sys
from PyQt5.QtWidgets import QApplication
from gui.tabbed_interface import TabbedInterface

def main():
    app = QApplication(sys.argv)
    tabbed_interface = TabbedInterface()
    tabbed_interface.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
