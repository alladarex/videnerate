from threading import Event

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.export_settings import ExportSettings
from core.models.project import Project
from core.project_paths import ProjectPaths
from services.export_service import ExportCancelled, export_project
from ui.styles.qss import ACTION_BUTTON


class ExportWorker(QObject):
    progress = Signal(int, int, str)
    finished = Signal(str)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(
        self,
        project: Project,
        paths: ProjectPaths,
        settings: ExportSettings,
        cancel_event: Event,
    ) -> None:
        super().__init__()
        self._project = project
        self._paths = paths
        self._settings = settings
        self._cancel_event = cancel_event

    def cancel(self) -> None:
        self._cancel_event.set()

    @Slot()
    def run(self) -> None:
        try:
            output_path = export_project(
                self._project,
                self._paths,
                self._settings,
                on_progress=lambda phase, pct, msg: self.progress.emit(phase, pct, msg),
                cancel_event=self._cancel_event,
            )
        except ExportCancelled:
            self.cancelled.emit()
            return
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(str(output_path))


class ExportDialog(QDialog):
    """Collect export settings then run the export with a progress bar."""

    def __init__(
        self, project: Project, paths: ProjectPaths, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._project = project
        self._paths = paths
        self._thread: QThread | None = None
        self._worker: ExportWorker | None = None
        self._export_running = False
        self._cancel_event: Event | None = None
        self._current_phase = 0
        self._close_after_cancel = False

        self.setWindowTitle("Export settings")
        self.setModal(True)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.resize(360, 180)

        self._subtitles_checkbox = QCheckBox("Subtitles", self)
        self._cancel_btn = QPushButton("Cancel", self)
        self._export_btn = QPushButton("Export", self)
        self._stack = QStackedWidget(self)
        self._progress_bar = QProgressBar(self)
        self._progress_label = QLabel("Exporting...", self)
        self._progress_cancel_btn = QPushButton("Cancel", self)
        self._ok_btn = QPushButton("OK", self)

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        settings_view = QWidget(self)
        settings_view_layout = QVBoxLayout(settings_view)
        settings_view_layout.setContentsMargins(0, 0, 0, 0)
        settings_view_layout.setSpacing(16)
        settings_view_layout.addWidget(self._subtitles_checkbox)
        settings_view_layout.addStretch()
        buttons_row = QWidget(self)
        buttons_row_layout = QHBoxLayout(buttons_row)
        buttons_row_layout.setContentsMargins(0, 0, 0, 0)
        self._cancel_btn.setStyleSheet(ACTION_BUTTON)
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.clicked.connect(self._on_cancel_clicked)
        self._export_btn.setStyleSheet(ACTION_BUTTON)
        self._export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._export_btn.clicked.connect(self._start_export)
        buttons_row_layout.addWidget(self._cancel_btn)
        buttons_row_layout.addStretch()
        buttons_row_layout.addWidget(self._export_btn)
        settings_view_layout.addWidget(buttons_row)

        progress_view = QWidget(self)
        progress_view_layout = QVBoxLayout(progress_view)
        progress_view_layout.setContentsMargins(0, 0, 0, 0)
        progress_view_layout.setSpacing(8)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFormat("%p%")
        progress_view_layout.addWidget(self._progress_label)
        progress_view_layout.addWidget(self._progress_bar)
        progress_button_row = QWidget(self)
        progress_button_row_layout = QHBoxLayout(progress_button_row)
        progress_button_row_layout.setContentsMargins(0, 0, 0, 0)
        self._progress_cancel_btn.setStyleSheet(ACTION_BUTTON)
        self._progress_cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._progress_cancel_btn.clicked.connect(self._on_cancel_clicked)
        progress_button_row_layout.addWidget(self._progress_cancel_btn)
        progress_button_row_layout.addStretch()
        progress_view_layout.addWidget(progress_button_row)

        finished_view = QWidget(self)
        finished_view_layout = QVBoxLayout(finished_view)
        finished_view_layout.setContentsMargins(0, 0, 0, 0)
        finished_view_layout.setSpacing(12)
        self._finished_label = QLabel(self)
        self._finished_label.setWordWrap(True)
        finished_view_layout.addWidget(self._finished_label)
        ok_row = QHBoxLayout()
        ok_row.setContentsMargins(0, 0, 0, 0)
        self._ok_btn.setStyleSheet(ACTION_BUTTON)
        self._ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ok_btn.clicked.connect(self.accept)
        ok_row.addStretch()
        ok_row.addWidget(self._ok_btn)
        finished_view_layout.addLayout(ok_row)

        self._stack.addWidget(settings_view)
        self._stack.addWidget(progress_view)
        self._stack.addWidget(finished_view)
        self._stack.setCurrentIndex(0)
        layout.addWidget(self._stack)

    def _start_export(self) -> None:
        if self._thread is not None:
            return

        self._export_running = True
        self._close_after_cancel = False
        self._stack.setCurrentIndex(1)
        self._subtitles_checkbox.setEnabled(False)
        self._cancel_btn.setEnabled(True)
        self._current_phase = 1
        self._progress_bar.setValue(0)
        self._progress_bar.setFormat("%p% (1/2)")
        self._progress_label.setText("Starting export...")

        self._cancel_event = Event()
        self._thread = QThread()
        self._worker = ExportWorker(
            self._project,
            self._paths,
            ExportSettings(subtitles=self._subtitles_checkbox.isChecked()),
            cancel_event=self._cancel_event,
        )
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.cancelled.connect(self._on_cancelled)
        self._thread.start()

    @Slot(int, int, str)
    def _on_progress(self, phase: int, percent: int, message: str) -> None:
        if phase != self._current_phase:
            self._current_phase = phase
            self._progress_bar.setValue(0)
        self._progress_bar.setFormat(f"%p% ({phase}/2)")
        self._progress_bar.setValue(percent)
        self._progress_label.setText(message)

    def _stop_worker_thread(self) -> None:
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
            self._thread.deleteLater()
            self._thread = None
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None
        self._export_running = False
        self._cancel_event = None

    @Slot(str)
    def _on_finished(self, output_path: str) -> None:
        self._stop_worker_thread()
        self.setWindowTitle("Export complete")
        self._finished_label.setText(f"Export complete.\n\nVideo saved to:\n{output_path}")
        self._stack.setCurrentIndex(2)

    @Slot(str)
    def _on_failed(self, error_message: str) -> None:
        self._stop_worker_thread()
        self.setWindowTitle("Export failed")
        self._finished_label.setText(f"Export failed.\n\n{error_message}")
        self._stack.setCurrentIndex(2)

    @Slot()
    def _on_cancelled(self) -> None:
        self._stop_worker_thread()
        if self._close_after_cancel:
            self.reject()
            return
        self._stack.setCurrentIndex(0)
        self._subtitles_checkbox.setEnabled(True)
        self._cancel_btn.setEnabled(True)

    def _confirm_cancel(self) -> bool:
        return (
            QMessageBox.question(
                self,
                "Stop export?",
                "Do you want to stop exporting?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            == QMessageBox.StandardButton.Yes
        )

    def _on_cancel_clicked(self) -> None:
        if not self._export_running:
            self.reject()
            return
        if not self._confirm_cancel():
            return
        self._close_after_cancel = False
        if self._worker is not None:
            self._worker.cancel()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._export_running:
            if not self._confirm_cancel():
                event.ignore()
                return
            self._close_after_cancel = True
            if self._worker is not None:
                self._worker.cancel()
            event.ignore()
            return
        self._stop_worker_thread()
        super().closeEvent(event)