from PySide6.QtCore import Signal, Slot
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
from ui.utils.background_task import run_in_thread
from ui.widgets.start_flow_widgets import (
    NarrationEditorView,
    StartHomeView,
    VideoIdeaView,
)
from ui.windows.project_window import ProjectWindow


class StartWindow(QMainWindow):
    """Start screen with new-project actions and project loader."""

    # Progress messages emitted from the project-creation thread.
    status_changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Videnerate")
        self.resize(900, 520)

        self._stack = QStackedWidget()
        self._home_view = StartHomeView(self)
        self._video_idea_view = VideoIdeaView(self)
        self._narration_view = NarrationEditorView(self)

        self._is_generating_narration = False
        self._narration_back_target_index = 1

        self._is_creating_project = False
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

        self.status_changed.connect(self._narration_view.set_loading_status)

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

        if self._is_generating_narration:
            return

        self._is_generating_narration = True
        self._video_idea_view.set_loading(True)
        selected_model = self._video_idea_view.get_selected_model()

        run_in_thread(
            lambda: generate_narration(video_idea, selected_model=selected_model),
            on_success=self._on_narration_generated,
            on_error=self._on_narration_generation_failed,
        )

    def _on_narration_generated(self, narration: str) -> None:
        self._is_generating_narration = False
        self._video_idea_view.set_loading(False)
        self._narration_view.narration_editor.setPlainText(narration)
        self._narration_back_target_index = 1
        self._narration_view.set_project_title(get_next_project_title())
        self._stack.setCurrentIndex(2)

    def _on_narration_generation_failed(self, error: Exception) -> None:
        self._is_generating_narration = False
        self._video_idea_view.set_loading(False)
        QMessageBox.critical(
            self,
            "Narration generation failed",
            f"Unable to generate narration.\n\n{error}",
        )

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

        if self._is_creating_project:
            return

        self._is_creating_project = True
        self._narration_view.set_loading(True)
        selected_model = self._narration_view.get_selected_model()
        auto_assign = self._narration_view.is_auto_assign_checked()

        def create_project() -> Project:
            self.status_changed.emit("Segmenting narration...")
            segments = generate_segments(narration, selected_model=selected_model)
            return create_and_save_project(
                segments,
                title=project_title,
                narration=narration,
                auto_assign=auto_assign,
                selected_model=selected_model,
                on_status=self.status_changed.emit,
            )

        run_in_thread(
            create_project,
            on_success=self._on_project_created,
            on_error=self._on_project_creation_failed,
        )

    def _on_project_created(self, project: Project) -> None:
        self._is_creating_project = False
        self._narration_view.set_loading(False)
        self._project_window = ProjectWindow(project)
        self._project_window.showMaximized()
        self.close()

    def _on_project_creation_failed(self, error: Exception) -> None:
        self._is_creating_project = False
        self._narration_view.set_loading(False)
        QMessageBox.critical(
            self,
            "Project creation failed",
            f"Unable to create project.\n\n{error}",
        )
