from __future__ import annotations
import asyncio
from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QToolBar, QWidget, QVBoxLayout,
    QMessageBox, QApplication,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction

from .session import AlexaSession
from .store import IntegrationStore
from .view_model import DeviceListViewModel
from .login_dialog import LoginDialog
from .device_list_view import DeviceListView
from .sidebar import Sidebar
from .batch_bar import BatchActionsBar
from .models.filter import DeviceFilter, BatchAction
from .models.device import Device


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Alexa Device Manager")
        self.setMinimumSize(900, 600)
        self.resize(1100, 700)

        # Core
        self.session = AlexaSession()
        self.store = IntegrationStore()
        self.view_model = DeviceListViewModel(self.session, self.store)

        # UI
        self._setup_ui()
        self._setup_toolbar()
        self._connect_signals()

    def start(self) -> None:
        asyncio.ensure_future(self._auto_login())

    def _setup_ui(self) -> None:
        splitter = QSplitter(Qt.Horizontal)

        self.sidebar = Sidebar(self.view_model, self.store)
        splitter.addWidget(self.sidebar)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.device_list = DeviceListView(self.view_model)
        right_layout.addWidget(self.device_list, 1)

        self.batch_bar = BatchActionsBar(self.view_model)
        right_layout.addWidget(self.batch_bar)

        splitter.addWidget(right_panel)
        splitter.setSizes([280, 620])

        self.setCentralWidget(splitter)

    def _setup_toolbar(self) -> None:
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(toolbar)

        self.sign_in_action = QAction("Sign in", self)
        self.sign_in_action.triggered.connect(self._show_login)
        toolbar.addAction(self.sign_in_action)

        self.refresh_action = QAction("Refresh", self)
        self.refresh_action.triggered.connect(self._refresh)
        self.refresh_action.setEnabled(False)
        toolbar.addAction(self.refresh_action)

        self.fields_action = QAction("Check Fields", self)
        self.fields_action.triggered.connect(self._check_fields)
        self.fields_action.setEnabled(False)
        toolbar.addAction(self.fields_action)

    def _connect_signals(self) -> None:
        self.session.is_logged_in.connect(self._on_login_changed)
        self.device_list.selection_changed.connect(self._on_selection_changed)
        self.view_model.devices_changed.connect(self._on_devices_changed)
        self.view_model.groups_changed.connect(self._on_groups_changed)
        self.view_model.busy_changed.connect(self._on_busy)
        self.view_model.status_message.connect(lambda msg: self.statusBar().showMessage(msg, 5000))

        self.sidebar.filter_changed.connect(self._on_filter_changed)

        self.batch_bar.delete_selected.connect(self._delete_selected)
        self.batch_bar.delete_unresponsive.connect(self._delete_unresponsive)
        self.batch_bar.delete_disabled.connect(self._delete_disabled)
        self.batch_bar.delete_all.connect(self._delete_all)
        self.batch_bar.add_to_group.connect(self._add_to_group)
        self.batch_bar.remove_from_group.connect(self._remove_from_group)
        self.batch_bar.create_group_from_selection.connect(self._create_group_from_selection)

    def _on_login_changed(self, logged_in: bool) -> None:
        self.sign_in_action.setText("Signed in" if logged_in else "Sign in")
        self.refresh_action.setEnabled(logged_in)
        self.fields_action.setEnabled(logged_in)

    def _on_devices_changed(self) -> None:
        self.device_list.set_devices(self.view_model.devices)
        self.batch_bar.update_counts(len(self.device_list.selected_devices()))

    def _on_groups_changed(self) -> None:
        self.batch_bar.update_counts(len(self.device_list.selected_devices()))

    def _on_selection_changed(self) -> None:
        self.batch_bar.update_counts(len(self.device_list.selected_devices()))

    def _on_busy(self, busy: bool) -> None:
        self.refresh_action.setEnabled(not busy and self.session.is_logged_in)

    def _on_filter_changed(self, filter_value: DeviceFilter) -> None:
        devices = self.view_model.devices
        if filter_value.kind == "all":
            filtered = devices
        elif filter_value.kind == "skill":
            filtered = [d for d in devices if d.integration_group_key == filter_value.value]
        elif filter_value.kind == "type":
            filtered = [d for d in devices if d.type_label == filter_value.value]
        elif filter_value.kind == "group":
            filtered = self.view_model.devices_in_group(filter_value.value)
        elif filter_value.kind == "unresponsive":
            filtered = self.view_model.unresponsive_devices()
        elif filter_value.kind == "disabledIntegrations":
            filtered = self.view_model.devices_from_disabled_integrations()
        else:
            filtered = devices
        self.device_list.set_devices(filtered)

    def _show_login(self) -> None:
        if hasattr(self, "_login_dialog") and self._login_dialog and self._login_dialog.isVisible():
            self._login_dialog.raise_()
            return
        self._login_dialog = LoginDialog(self.session, self)
        self._login_dialog.finished.connect(self._on_login_finished)
        self._login_dialog.show()

    def _on_login_finished(self, result: int) -> None:
        self._login_dialog = None

    async def _auto_login(self) -> None:
        already = await self.session.attempt_auto_login()
        if already:
            await self.view_model.refresh()
        else:
            self._show_login()

    async def _refresh(self) -> None:
        await self.view_model.refresh()

    async def _check_fields(self) -> None:
        try:
            text = await self.session.fetch_all_endpoint_field_names()
            QMessageBox.information(self, "Available Fields", text)
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _confirm_batch_delete(self, action: BatchAction) -> None:
        devices = self._target_devices(action)
        if not devices:
            return
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Really delete {len(devices)} device(s)? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            asyncio.ensure_future(self.view_model.delete_devices(devices))

    def _target_devices(self, action: BatchAction) -> list[Device]:
        if action.kind == "selected":
            return self.device_list.selected_devices()
        elif action.kind == "unresponsive":
            return self.view_model.unresponsive_devices()
        elif action.kind == "disabledIntegrations":
            return self.view_model.devices_from_disabled_integrations()
        elif action.kind == "all":
            return self.view_model.devices
        return action.devices or []

    def _delete_selected(self) -> None:
        self._confirm_batch_delete(BatchAction("selected", self.device_list.selected_devices()))

    def _delete_unresponsive(self) -> None:
        self._confirm_batch_delete(BatchAction.unresponsive())

    def _delete_disabled(self) -> None:
        self._confirm_batch_delete(BatchAction.disabled_integrations())

    def _delete_all(self) -> None:
        self._confirm_batch_delete(BatchAction.all())

    async def _add_to_group(self, group_id: str, group) -> None:
        devices = self.device_list.selected_devices()
        await self.view_model.add_devices(devices, to_group=group)

    async def _remove_from_group(self, group_id: str, group) -> None:
        devices = self.device_list.selected_devices()
        await self.view_model.remove_devices(devices, from_group=group)

    async def _create_group_from_selection(self, name: str) -> None:
        devices = self.device_list.selected_devices()
        await self.view_model.create_group(name=name, members=devices)
