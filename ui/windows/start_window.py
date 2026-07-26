from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtWidgets import QMainWindow, QMessageBox, QStackedWidget

from core.models.project import Project
from services.llm_service import generate_narration, generate_segments
from services.project_service import (
    create_and_save_project,
    get_next_project_title,
    is_project_title_unique,
    list_project_titles,
    load_project,
    validate_project_title_for_storage,
)
from ui.widgets.start_flow_widgets import (
    NarrationEditorView,
    StartHomeView,
    VideoIdeaView,
)
from ui.windows.project_window import ProjectWindow


class NarrationGenerationWorker(QObject):
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, video_idea: str, selected_model: str) -> None:
        super().__init__()
        self._video_idea = video_idea
        self._selected_model = selected_model

    @Slot()
    def run(self) -> None:
        try:
            narration = generate_narration(
                self._video_idea, selected_model=self._selected_model
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(narration)


class ProjectCreationWorker(QObject):
    finished = Signal(Project)
    failed = Signal(str)
    status = Signal(str)

    def __init__(
        self,
        narration: str,
        project_title: str,
        selected_model: str,
        auto_assign: bool,
    ) -> None:
        super().__init__()
        self._narration = narration
        self._project_title = project_title
        self._selected_model = selected_model
        self._auto_assign = auto_assign

    @Slot()
    def run(self) -> None:
        try:
            self.status.emit("Segmenting narration...")
            segments = generate_segments(
                self._narration, selected_model=self._selected_model
            )
            project = create_and_save_project(
                segments,
                title=self._project_title,
                narration=self._narration,
                auto_assign=self._auto_assign,
                selected_model=self._selected_model,
                on_status=self.status.emit,
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(project)


class StartWindow(QMainWindow):
    """Start screen with new-project actions and project loader."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Videnerate")
        self.resize(900, 520)

        self._stack = QStackedWidget()
        self._home_view = StartHomeView(self)
        self._video_idea_view = VideoIdeaView(self)
        self._narration_view = NarrationEditorView(self)

        self._generation_thread: QThread | None = None
        self._generation_worker: NarrationGenerationWorker | None = None
        self._narration_back_target_index = 1

        self._project_thread: QThread | None = None
        self._project_worker: ProjectCreationWorker | None = None
        self._project_window: ProjectWindow | None = None

        self._build_ui()
        self._load_projects()
        self._center_on_screen()

    def _build_ui(self) -> None:
        self._home_view.enter_video_idea_clicked.connect(self._on_enter_video_idea)
        self._home_view.enter_narration_clicked.connect(self._on_enter_narration)
        self._home_view.upload_audio_clicked.connect(self._on_upload_audio_file)
        self._home_view.project_activated.connect(self._on_project_selected)

        self._video_idea_view.back_clicked.connect(self._on_back_to_start)
        self._video_idea_view.generate_clicked.connect(self._on_generate_video_idea)

        self._narration_view.back_clicked.connect(self._on_back_from_narration_view)
        self._narration_view.create_project_clicked.connect(self._on_create_project)

        self.setCentralWidget(self._stack)
        self._stack.addWidget(self._home_view)
        self._stack.addWidget(self._video_idea_view)
        self._stack.addWidget(self._narration_view)
        self._stack.setCurrentIndex(0)

    def _load_projects(self) -> None:
        self._home_view.projects_list.clear()

        projects = list_project_titles()

        if projects:
            self._home_view.projects_list.addItems(projects)
            self._home_view.projects_list.show()
            self._home_view.empty_projects_label.hide()
        else:
            self._home_view.projects_list.hide()
            self._home_view.empty_projects_label.show()

    @Slot(str)
    def _on_project_selected(self, title: str) -> None:
        """Open an existing project from the list and close the start window."""
        try:
            project = load_project(title)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Unable to load project",
                f"Could not open project '{title}'.\n\n{exc}",
            )
            return

        self._project_window = ProjectWindow(project)
        self._project_window.showMaximized()
        self.close()

    def _center_on_screen(self) -> None:
        screen = self.screen()
        if screen is None:
            return
        frame = self.frameGeometry()
        frame.moveCenter(screen.availableGeometry().center())
        self.move(frame.topLeft())

    def _on_enter_video_idea(self) -> None:
        self._stack.setCurrentIndex(1)

    def _on_enter_narration(self) -> None:
        self._narration_back_target_index = 0
        self._narration_view.set_project_title(
            get_next_project_title()
        )
        self._stack.setCurrentIndex(2)

    def _on_upload_audio_file(self) -> None:
        pass

    def _on_back_to_start(self) -> None:
        self._stack.setCurrentIndex(0)

    def _on_generate_video_idea(self) -> None:
        video_idea = self._video_idea_view.video_idea_input.toPlainText().strip()
        if not video_idea:
            QMessageBox.warning(self, "Missing input", "Please enter a video idea first.")
            return

        if self._generation_thread is not None:
            return

        self._video_idea_view.set_loading(True)

        self._generation_thread = QThread(self)
        self._generation_worker = NarrationGenerationWorker(
            video_idea, selected_model=self._video_idea_view.get_selected_model()
        )
        self._generation_worker.moveToThread(self._generation_thread)

        self._generation_thread.started.connect(self._generation_worker.run)
        self._generation_worker.finished.connect(self._on_narration_generated)
        self._generation_worker.failed.connect(self._on_narration_generation_failed)
        self._generation_worker.finished.connect(self._cleanup_generation_thread)
        self._generation_worker.failed.connect(self._cleanup_generation_thread)
        self._generation_thread.start()

    @Slot(str)
    def _on_narration_generated(self, narration: str) -> None:
        self._narration_view.narration_editor.setPlainText(narration)
        self._narration_back_target_index = 1
        self._narration_view.set_project_title(
            get_next_project_title()
        )
        self._stack.setCurrentIndex(2)

    @Slot(str)
    def _on_narration_generation_failed(self, error_message: str) -> None:
        QMessageBox.critical(
            self,
            "Narration generation failed",
            f"Unable to generate narration.\n\n{error_message}",
        )

    @Slot()
    def _cleanup_generation_thread(self) -> None:
        self._video_idea_view.set_loading(False)

        if self._generation_thread is not None:
            self._generation_thread.quit()
            self._generation_thread.wait()
            self._generation_thread.deleteLater()
            self._generation_thread = None

        if self._generation_worker is not None:
            self._generation_worker.deleteLater()
            self._generation_worker = None

    def _on_back_from_narration_view(self) -> None:
        self._stack.setCurrentIndex(self._narration_back_target_index)

    def _on_create_project(self) -> None:
        narration = self._narration_view.narration_editor.toPlainText().strip()
        if not narration:
            QMessageBox.warning(
                self,
                "Missing input",
                "Please enter narration first.",
            )
            return

        project_title = self._narration_view.get_project_title()
        if not project_title:
            project_title = get_next_project_title()
            self._narration_view.set_project_title(project_title)

        try:
            project_title = validate_project_title_for_storage(project_title)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid project title", str(exc))
            return

        self._narration_view.set_project_title(project_title)

        if not is_project_title_unique(project_title):
            QMessageBox.warning(
                self,
                "Project title already exists",
                (
                    "A project folder with this title already exists.\n"
                    "Please choose a different title."
                ),
            )
            return

        if self._project_thread is not None:
            return

        self._narration_view.set_loading(True)

        self._project_thread = QThread(self)
        self._project_worker = ProjectCreationWorker(
            narration,
            project_title,
            selected_model=self._narration_view.get_selected_model(),
            auto_assign=self._narration_view.is_auto_assign_checked(),
        )
        self._project_worker.moveToThread(self._project_thread)

        self._project_thread.started.connect(self._project_worker.run)
        self._project_worker.status.connect(self._narration_view.set_loading_status)
        self._project_worker.finished.connect(self._on_project_created)
        self._project_worker.failed.connect(self._on_project_creation_failed)
        self._project_worker.finished.connect(self._cleanup_project_thread)
        self._project_worker.failed.connect(self._cleanup_project_thread)
        self._project_thread.start()

    @Slot(Project)
    def _on_project_created(self, project: Project) -> None:
        self._project_window = ProjectWindow(project)
        self._project_window.showMaximized()
        self.close()

    @Slot(str)
    def _on_project_creation_failed(self, error_message: str) -> None:
        QMessageBox.critical(
            self,
            "Project creation failed",
            f"Unable to create project.\n\n{error_message}",
        )

    @Slot()
    def _cleanup_project_thread(self) -> None:
        self._narration_view.set_loading(False)

        if self._project_thread is not None:
            self._project_thread.quit()
            self._project_thread.wait()
            self._project_thread.deleteLater()
            self._project_thread = None

        if self._project_worker is not None:
            self._project_worker.deleteLater()
            self._project_worker = None
