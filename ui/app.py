import sys

from PySide6.QtWidgets import QApplication

from ui.windows.start_window import StartWindow


def run() -> int:
    app = QApplication(sys.argv)
    window = StartWindow()
    window.show()
    return app.exec()
