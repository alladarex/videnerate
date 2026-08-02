from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.styles.qss import ACTION_BUTTON

_WARNING_TEXT = (
    "Some segments have no media attached.\n"
    "They will be blank (black screen) while the voiceover plays.\n\n"
    "Do you want to proceed?"
)


class MissingMediaDialog(QDialog):
    """Warn the user about segments without media and ask whether to proceed."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Missing media")
        self.setModal(True)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        message = QLabel(_WARNING_TEXT, self)
        message.setWordWrap(True)
        layout.addWidget(message)

        cancel_btn = QPushButton("Cancel", self)
        cancel_btn.setStyleSheet(ACTION_BUTTON)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)

        proceed_btn = QPushButton("Proceed", self)
        proceed_btn.setStyleSheet(ACTION_BUTTON)
        proceed_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        proceed_btn.clicked.connect(self.accept)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.addWidget(cancel_btn)
        button_row.addStretch()
        button_row.addWidget(proceed_btn)
        layout.addLayout(button_row)
