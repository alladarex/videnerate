from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QSpinBox,
    QWidget,
    QWidgetAction,
)


@dataclass
class SearchSettingsState:
    """Persisted across segment switches and segment view rebuilds."""

    google: bool = True
    giphy: bool = False
    pexels_video: bool = True
    pexels_image: bool = True
    pixabay_video: bool = True
    pixabay_image: bool = True
    limit: int = 16


_state = SearchSettingsState()


def search_settings_state() -> SearchSettingsState:
    return _state


def _providers_active(state: SearchSettingsState) -> bool:
    """True if at least one search provider is enabled (Pexels/Pixabay count if either Video or Image)."""
    return bool(
        state.google
        or state.giphy
        or (state.pexels_video or state.pexels_image)
        or (state.pixabay_video or state.pixabay_image)
    )


def _ensure_at_least_one_provider(*, state: SearchSettingsState, google_act: QAction) -> None:
    if _providers_active(state):
        return
    google_act.blockSignals(True)
    google_act.setChecked(True)
    google_act.blockSignals(False)
    state.google = True


class _SearchSettingsMenu(QMenu):
    """Checkable actions toggle without dismissing the menu (standard QMenu closes on trigger)."""

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            act = self.actionAt(event.pos())
            if act is not None and act.isEnabled() and act.isCheckable():
                act.setChecked(not act.isChecked())
                event.accept()
                return
        super().mouseReleaseEvent(event)


def _add_checkable(menu: QMenu, text: str) -> QAction:
    act = QAction(text, menu)
    act.setCheckable(True)
    act.setChecked(True)
    menu.addAction(act)
    return act


def _add_limit_row(menu: QMenu) -> QSpinBox:
    row = QWidget(menu)
    layout = QHBoxLayout(row)
    layout.setContentsMargins(12, 4, 12, 4)
    layout.setSpacing(8)

    label = QLabel("Limit", row)
    layout.addWidget(label, 0)

    spin = QSpinBox(row)
    spin.setRange(4, 30)
    spin.setValue(16)
    spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
    spin.setFixedWidth(44)
    spin.setAlignment(Qt.AlignmentFlag.AlignRight)
    layout.addWidget(spin, 0)

    action = QWidgetAction(menu)
    action.setDefaultWidget(row)
    menu.addAction(action)
    return spin


def _wire_parent_submenu_sync(parent: QAction, video: QAction, image: QAction) -> None:
    """Parent toggles both children; children OR-gate the parent."""

    syncing = False

    def on_parent(checked: bool) -> None:
        nonlocal syncing
        if syncing:
            return
        syncing = True
        try:
            video.setChecked(checked)
            image.setChecked(checked)
        finally:
            syncing = False

    def on_child() -> None:
        nonlocal syncing
        if syncing:
            return
        syncing = True
        try:
            parent.setChecked(video.isChecked() or image.isChecked())
        finally:
            syncing = False

    parent.toggled.connect(on_parent)
    video.toggled.connect(on_child)
    image.toggled.connect(on_child)


def _apply_persisted_state(
    *,
    google_act: QAction,
    giphy_act: QAction,
    pexels_video: QAction,
    pexels_image: QAction,
    pixabay_video: QAction,
    pixabay_image: QAction,
    limit_spin: QSpinBox,
) -> None:
    s = _state
    google_act.setChecked(s.google)
    giphy_act.setChecked(s.giphy)
    pexels_video.setChecked(s.pexels_video)
    pexels_image.setChecked(s.pexels_image)
    pixabay_video.setChecked(s.pixabay_video)
    pixabay_image.setChecked(s.pixabay_image)
    limit_spin.setValue(s.limit)

    _ensure_at_least_one_provider(state=s, google_act=google_act)


def _connect_state_persistence(
    *,
    google_act: QAction,
    giphy_act: QAction,
    pexels_video: QAction,
    pexels_image: QAction,
    pixabay_video: QAction,
    pixabay_image: QAction,
    limit_spin: QSpinBox,
) -> None:
    def sync_from_actions() -> None:
        _state.google = google_act.isChecked()
        _state.giphy = giphy_act.isChecked()
        _state.pexels_video = pexels_video.isChecked()
        _state.pexels_image = pexels_image.isChecked()
        _state.pixabay_video = pixabay_video.isChecked()
        _state.pixabay_image = pixabay_image.isChecked()

        _ensure_at_least_one_provider(state=_state, google_act=google_act)

    google_act.toggled.connect(lambda _: sync_from_actions())
    giphy_act.toggled.connect(lambda _: sync_from_actions())
    pexels_video.toggled.connect(lambda _: sync_from_actions())
    pexels_image.toggled.connect(lambda _: sync_from_actions())
    pixabay_video.toggled.connect(lambda _: sync_from_actions())
    pixabay_image.toggled.connect(lambda _: sync_from_actions())
    limit_spin.valueChanged.connect(lambda v: setattr(_state, "limit", int(v)))


def build_search_settings_menu(parent: QWidget) -> QMenu:
    menu = _SearchSettingsMenu(parent)

    google_act = _add_checkable(menu, "Google")
    giphy_act = _add_checkable(menu, "Giphy")

    pexels = _SearchSettingsMenu(menu)
    pexels_video = _add_checkable(pexels, "Video")
    pexels_image = _add_checkable(pexels, "Image")
    pexels_act = QAction("Pexels", menu)
    pexels_act.setCheckable(True)
    pexels_act.setChecked(True)
    pexels_act.setMenu(pexels)
    menu.addAction(pexels_act)
    _wire_parent_submenu_sync(pexels_act, pexels_video, pexels_image)

    pixabay = _SearchSettingsMenu(menu)
    pixabay_video = _add_checkable(pixabay, "Video")
    pixabay_image = _add_checkable(pixabay, "Image")
    pixabay_act = QAction("Pixabay", menu)
    pixabay_act.setCheckable(True)
    pixabay_act.setChecked(True)
    pixabay_act.setMenu(pixabay)
    menu.addAction(pixabay_act)
    _wire_parent_submenu_sync(pixabay_act, pixabay_video, pixabay_image)

    menu.addSeparator()
    limit_spin = _add_limit_row(menu)
    menu.limit_spin = limit_spin

    _apply_persisted_state(
        google_act=google_act,
        giphy_act=giphy_act,
        pexels_video=pexels_video,
        pexels_image=pexels_image,
        pixabay_video=pixabay_video,
        pixabay_image=pixabay_image,
        limit_spin=limit_spin,
    )
    _connect_state_persistence(
        google_act=google_act,
        giphy_act=giphy_act,
        pexels_video=pexels_video,
        pexels_image=pexels_image,
        pixabay_video=pixabay_video,
        pixabay_image=pixabay_image,
        limit_spin=limit_spin,
    )

    return menu
