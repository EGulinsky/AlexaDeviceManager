from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QMenu, QProgressBar, QLabel,
    QInputDialog, QMessageBox,
)
from PySide6.QtCore import Signal, Qt
from PySide6 import QtWidgets

from .models.device import Device
from .models.filter import BatchAction
from .view_model import DeviceListViewModel


class BatchActionsBar(QWidget):
    delete_selected = Signal()
    delete_unresponsive = Signal()
    delete_disabled = Signal()
    delete_all = Signal()
    add_to_group = Signal(str, object)
    remove_from_group = Signal(str, object)
    create_group_from_selection = Signal(str)

    def __init__(self, view_model: DeviceListViewModel, parent=None):
        super().__init__(parent)
        self._view_model = view_model

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(200)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: gray; font-size: 11px;")
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)

        spacer = QWidget()
        spacer.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        layout.addWidget(spacer, 1)

        self.delete_sel_btn = QPushButton("Delete Selected (0)")
        self.delete_sel_btn.clicked.connect(self.delete_selected.emit)
        layout.addWidget(self.delete_sel_btn)

        self.delete_unr_btn = QPushButton("Delete Not Responding (0)")
        self.delete_unr_btn.clicked.connect(self.delete_unresponsive.emit)
        layout.addWidget(self.delete_unr_btn)

        self.delete_dis_btn = QPushButton("Delete Disabled Integrations (0)")
        self.delete_dis_btn.clicked.connect(self.delete_disabled.emit)
        layout.addWidget(self.delete_dis_btn)

        self.groups_menu_btn = QPushButton("Groups (0)")
        self.groups_menu = QMenu(self)
        self.groups_menu.triggered.connect(self._on_groups_menu_action)
        self._build_groups_menu([])
        self.groups_menu_btn.setMenu(self.groups_menu)
        layout.addWidget(self.groups_menu_btn)

        self.delete_all_btn = QPushButton("Delete All (0)")
        self.delete_all_btn.clicked.connect(self.delete_all.emit)
        layout.addWidget(self.delete_all_btn)

        self._view_model.status_message.connect(self._on_status)
        self._view_model.progress_changed.connect(self._on_progress)

    def update_counts(self, selected_count: int) -> None:
        self.delete_sel_btn.setText(f"Delete Selected ({selected_count})")
        self.delete_sel_btn.setEnabled(selected_count > 0 and not self._view_model.is_busy)

        unresponsive = len(self._view_model.unresponsive_devices())
        self.delete_unr_btn.setText(f"Delete Not Responding ({unresponsive})")
        self.delete_unr_btn.setEnabled(unresponsive > 0 and not self._view_model.is_busy)

        disabled = len(self._view_model.devices_from_disabled_integrations())
        self.delete_dis_btn.setText(f"Delete Disabled Integrations ({disabled})")
        self.delete_dis_btn.setEnabled(disabled > 0 and not self._view_model.is_busy)

        self.delete_all_btn.setText(f"Delete All ({len(self._view_model.devices)})")
        self.delete_all_btn.setEnabled(bool(self._view_model.devices) and not self._view_model.is_busy)

        self.groups_menu_btn.setText(f"Groups ({selected_count})")
        self.groups_menu_btn.setEnabled(selected_count > 0 and not self._view_model.is_busy)

        self._build_groups_menu([] if selected_count == 0 else None)

    def _build_groups_menu(self, selected: list[Device] | None) -> None:
        self.groups_menu.clear()

        add_menu = self.groups_menu.addMenu("Add to Group")
        if not self._view_model.device_groups:
            add_menu.addAction("No groups yet").setEnabled(False)
        for g, _ in self._view_model.grouped_by_device_group:
            action = add_menu.addAction(g.name)
            action.setData(("add", g))

        remove_menu = self.groups_menu.addMenu("Remove from Group")
        if not self._view_model.device_groups:
            remove_menu.addAction("No groups yet").setEnabled(False)
        for g, _ in self._view_model.grouped_by_device_group:
            action = remove_menu.addAction(g.name)
            action.setData(("remove", g))

        self.groups_menu.addSeparator()
        new_group_action = self.groups_menu.addAction("New Group from Selection...")
        new_group_action.setData(("new", None))

    def _on_groups_menu_action(self, action) -> None:
        data = action.data()
        if data is None:
            return
        kind, group = data

        if kind == "new":
            name, ok = QInputDialog.getText(self, "New Group", "Name:")
            if ok and name:
                self.create_group_from_selection.emit(name)
        elif kind == "add" and group:
            self.add_to_group.emit(group.id, group)
        elif kind == "remove" and group:
            self.remove_from_group.emit(group.id, group)

    def _on_status(self, message: str) -> None:
        self.status_label.setText(message)
        self.status_label.setVisible(bool(message))

    def _on_progress(self, done: int, total: int) -> None:
        if total > 0:
            self.progress_bar.setVisible(True)
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(done)
        else:
            self.progress_bar.setVisible(False)
