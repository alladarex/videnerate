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

from services.media_search import SEARCH_PROVIDERS, group_label, search_groups

# Switched back on when the user unchecks the last remaining source.
_FALLBACK_KEY = "web"


@dataclass
class SearchSettingsState:
    """Persisted across segment switches and segment view rebuilds."""

    enabled: set[str]
    limit: int = 16


# Sources checked the first time the menu opens (everything except Giphy)
_state = SearchSettingsState(
    enabled={"web", "pexels_video", "pexels_image", "pixabay_video", "pixabay_image"}
)


def search_settings_state() -> SearchSettingsState:
    return _state


def _ensure_at_least_one_source(actions: dict[str, QAction]) -> None:
    if _state.enabled:
        return
    action = actions[_FALLBACK_KEY]
    action.blockSignals(True)
    action.setChecked(True)
    action.blockSignals(False)
    _state.enabled = {_FALLBACK_KEY}


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


def _add_checkable(menu: QMenu, *, text: str, checked: bool) -> QAction:
    act = QAction(text, menu)
    act.setCheckable(True)
    act.setChecked(checked)
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
    spin.setValue(_state.limit)
    spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
    spin.setFixedWidth(44)
    spin.setAlignment(Qt.AlignmentFlag.AlignRight)
    layout.addWidget(spin, 0)

    action = QWidgetAction(menu)
    action.setDefaultWidget(row)
    menu.addAction(action)
    return spin


def _wire_parent_submenu_sync(parent: QAction, children: list[QAction]) -> None:
    """Parent toggles every child, children OR-gate the parent."""

    syncing = False

    def on_parent(checked: bool) -> None:
        nonlocal syncing
        if syncing:
            return
        syncing = True
        try:
            for child in children:
                child.setChecked(checked)
        finally:
            syncing = False

    def on_child() -> None:
        nonlocal syncing
        if syncing:
            return
        syncing = True
        try:
            parent.setChecked(any(child.isChecked() for child in children))
        finally:
            syncing = False

    parent.toggled.connect(on_parent)
    for child in children:
        child.toggled.connect(on_child)


def _add_group_row(menu: QMenu, *, group: str, keys: list[str]) -> dict[str, QAction]:
    """Add one top-level row and return the action per provider key it created.

    A group holding a single source is one checkable row, a group holding several is a
    checkable row with a submenu, where the row acts as a switch for all of them.
    """
    if len(keys) == 1:
        key = keys[0]
        action = _add_checkable(
            menu, text=group_label(group), checked=key in _state.enabled
        )
        return {key: action}

    submenu = _SearchSettingsMenu(menu)
    children = {
        key: _add_checkable(
            submenu, text=SEARCH_PROVIDERS[key].label, checked=key in _state.enabled
        )
        for key in keys
    }

    group_action = QAction(group_label(group), menu)
    group_action.setCheckable(True)
    group_action.setChecked(any(key in _state.enabled for key in keys))
    group_action.setMenu(submenu)
    menu.addAction(group_action)
    _wire_parent_submenu_sync(group_action, list(children.values()))
    return children


def build_search_settings_menu(parent: QWidget) -> QMenu:
    menu = _SearchSettingsMenu(parent)

    actions: dict[str, QAction] = {}
    for group, keys in search_groups().items():
        actions.update(_add_group_row(menu, group=group, keys=keys))

    menu.addSeparator()
    limit_spin = _add_limit_row(menu)

    def sync_from_actions() -> None:
        _state.enabled = {key for key, act in actions.items() if act.isChecked()}
        _ensure_at_least_one_source(actions)

    for action in actions.values():
        action.toggled.connect(lambda _: sync_from_actions())
    limit_spin.valueChanged.connect(lambda value: setattr(_state, "limit", int(value)))

    _ensure_at_least_one_source(actions)
    return menu