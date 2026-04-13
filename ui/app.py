import sys

from PySide6.QtCore import QLoggingCategory
from PySide6.QtWidgets import QApplication

from ui.windows.start_window import StartWindow


def run() -> int:
    # Some third-party images contain malformed ICC profiles, hide the warning
    QLoggingCategory.setFilterRules("qt.gui.icc=false")
    app = QApplication(sys.argv)
    window = StartWindow()
    window.show()
    return app.exec()
