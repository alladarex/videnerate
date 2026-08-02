from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from services.llm_service import (
    DEFAULT_NARRATION_MODEL,
    DEFAULT_SEGMENTATION_MODEL,
    SUPPORTED_MODELS,
)


class StartHomeView(QWidget):
    enter_video_idea_clicked = Signal()
    enter_narration_clicked = Signal()
    upload_audio_clicked = Signal()
    project_activated = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._projects_list = QListWidget()
        self._empty_projects_label = QLabel("No projects to load")
        self._empty_projects_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QGridLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setHorizontalSpacing(20)
        main_layout.setVerticalSpacing(20)

        create_project_box = QGroupBox("Create New Project")
        create_layout = QVBoxLayout()
        create_layout.setSpacing(12)

        btn_video_idea = QPushButton("Enter video idea")
        btn_narration = QPushButton("Enter narration")
        btn_upload_audio = QPushButton("Upload audio file")

        btn_video_idea.clicked.connect(self.enter_video_idea_clicked)
        btn_narration.clicked.connect(self.enter_narration_clicked)
        btn_upload_audio.clicked.connect(self.upload_audio_clicked)

        create_layout.addWidget(btn_video_idea)
        create_layout.addWidget(btn_narration)
        create_layout.addWidget(btn_upload_audio)
        create_layout.addStretch()
        create_project_box.setLayout(create_layout)

        load_project_box = QGroupBox("Load Project")
        load_layout = QVBoxLayout()
        load_layout.setSpacing(12)
        load_layout.addWidget(self._projects_list)
        load_layout.addWidget(self._empty_projects_label)
        load_project_box.setLayout(load_layout)

        self._projects_list.itemActivated.connect(
            lambda item: self.project_activated.emit(item.text())
        )

        main_layout.addWidget(create_project_box, 0, 0)
        main_layout.addWidget(load_project_box, 0, 1)
        main_layout.setColumnStretch(0, 1)
        main_layout.setColumnStretch(1, 1)

    def set_projects(self, titles: list[str]) -> None:
        """Show the loadable projects, or the empty notice when there are none."""
        self._projects_list.clear()
        self._projects_list.addItems(titles)
        self._projects_list.setVisible(bool(titles))
        self._empty_projects_label.setVisible(not titles)


class VideoIdeaView(QWidget):
    back_clicked = Signal()
    generate_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._video_idea_input = QPlainTextEdit()
        self._back_btn = QPushButton("Back")
        self._generate_btn = QPushButton("Generate")
        self._model_selector = QComboBox()
        self._action_stack = QStackedWidget()
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QGridLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setHorizontalSpacing(20)
        layout.setVerticalSpacing(12)

        self._back_btn.clicked.connect(self.back_clicked)
        back_row = QHBoxLayout()
        back_row.addWidget(self._back_btn)
        back_row.addStretch()
        layout.addLayout(back_row, 0, 0)

        self._video_idea_input.setPlaceholderText("Enter video idea...")
        layout.addWidget(self._video_idea_input, 1, 0)

        self._generate_btn.clicked.connect(self.generate_clicked)
        generate_row = QWidget(self)
        generate_row_layout = QHBoxLayout(generate_row)
        generate_row_layout.setContentsMargins(0, 0, 0, 0)
        generate_row_layout.addWidget(self._generate_btn)
        generate_row_layout.addStretch()
        self._model_selector.addItems(SUPPORTED_MODELS)
        self._model_selector.setCurrentText(DEFAULT_NARRATION_MODEL)
        generate_row_layout.addWidget(self._model_selector)

        loading_row = QWidget(self)
        loading_row_layout = QHBoxLayout(loading_row)
        loading_row_layout.setContentsMargins(0, 0, 0, 0)
        loading_label = QLabel("Generating...")
        loading_bar = QProgressBar()
        loading_bar.setRange(0, 0)
        loading_bar.setTextVisible(False)
        loading_bar.setFixedWidth(120)
        loading_row_layout.addWidget(loading_label)
        loading_row_layout.addWidget(loading_bar)
        loading_row_layout.addStretch()

        self._action_stack.addWidget(generate_row)
        self._action_stack.addWidget(loading_row)
        self._action_stack.setCurrentIndex(0)
        layout.addWidget(self._action_stack, 2, 0)
        layout.setRowStretch(1, 1)

    def set_loading(self, is_loading: bool) -> None:
        self._action_stack.setCurrentIndex(1 if is_loading else 0)
        self._back_btn.setEnabled(not is_loading)
        self._generate_btn.setEnabled(not is_loading)
        self._model_selector.setEnabled(not is_loading)

    def video_idea(self) -> str:
        return self._video_idea_input.toPlainText().strip()

    def selected_model(self) -> str:
        return self._model_selector.currentText()


class NarrationEditorView(QWidget):
    back_clicked = Signal()
    create_project_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._narration_editor = QPlainTextEdit()
        self._project_title_input = QLineEdit()
        self._back_btn = QPushButton("Back")
        self._create_project_btn = QPushButton("Create project")
        self._auto_assign_checkbox = QCheckBox("Auto-Assign")
        self._model_selector = QComboBox()
        self._action_stack = QStackedWidget()
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QGridLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setHorizontalSpacing(20)
        layout.setVerticalSpacing(12)

        self._back_btn.clicked.connect(self.back_clicked)
        back_row = QHBoxLayout()
        back_row.addWidget(self._back_btn)
        back_row.addStretch()
        layout.addLayout(back_row, 0, 0)

        layout.addWidget(self._narration_editor, 1, 0)

        self._create_project_btn.clicked.connect(self.create_project_clicked)
        create_project_row = QWidget(self)
        create_project_row_layout = QHBoxLayout(create_project_row)
        create_project_row_layout.setContentsMargins(0, 0, 0, 0)
        self._project_title_input.setFixedWidth(180)
        self._project_title_input.setPlaceholderText("Project title")
        create_project_row_layout.addWidget(self._project_title_input)
        create_project_row_layout.addWidget(self._create_project_btn)
        create_project_row_layout.addWidget(self._auto_assign_checkbox)
        create_project_row_layout.addStretch()
        self._model_selector.addItems(SUPPORTED_MODELS)
        self._model_selector.setCurrentText(DEFAULT_SEGMENTATION_MODEL)
        create_project_row_layout.addWidget(self._model_selector)

        loading_row = QWidget(self)
        loading_row_layout = QHBoxLayout(loading_row)
        loading_row_layout.setContentsMargins(0, 0, 0, 0)
        self._loading_label = QLabel("Creating project...")
        loading_bar = QProgressBar()
        loading_bar.setRange(0, 0)
        loading_bar.setTextVisible(False)
        loading_bar.setFixedWidth(160)
        loading_row_layout.addWidget(self._loading_label)
        loading_row_layout.addWidget(loading_bar)
        loading_row_layout.addStretch()

        self._action_stack.addWidget(create_project_row)
        self._action_stack.addWidget(loading_row)
        self._action_stack.setCurrentIndex(0)
        layout.addWidget(self._action_stack, 2, 0)
        layout.setRowStretch(1, 1)

    def set_loading(self, is_loading: bool) -> None:
        self._action_stack.setCurrentIndex(1 if is_loading else 0)
        self._back_btn.setEnabled(not is_loading)
        self._create_project_btn.setEnabled(not is_loading)
        self._project_title_input.setReadOnly(is_loading)
        self._model_selector.setEnabled(not is_loading)

    def set_loading_status(self, message: str) -> None:
        self._loading_label.setText(message)

    def narration(self) -> str:
        return self._narration_editor.toPlainText().strip()

    def set_narration(self, text: str) -> None:
        self._narration_editor.setPlainText(text)

    def set_project_title(self, title: str) -> None:
        self._project_title_input.setText(title)

    def project_title(self) -> str:
        return self._project_title_input.text().strip()

    def selected_model(self) -> str:
        return self._model_selector.currentText()

    def is_auto_assign_checked(self) -> bool:
        return self._auto_assign_checkbox.isChecked()
