from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QMenu,
    QInputDialog, QMessageBox,
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QDragEnterEvent, QDropEvent

from .models.device import Device
from .models.filter import DeviceFilter
from .view_model import DeviceListViewModel
from .store import IntegrationStore


class DeviceFilterItem(QTreeWidgetItem):
    def __init__(self, text: str, filter_value: DeviceFilter, device_count: int = 0):
        super().__init__([f"{text} ({device_count})" if device_count >= 0 else text])
        self.filter_value = filter_value
        self._base_text = text
        self._count = device_count

    def update_count(self, count: int) -> None:
        self._count = count
        self.setText(0, f"{self._base_text} ({count})" if count >= 0 else self._base_text)


class Sidebar(QWidget):
    filter_changed = Signal(DeviceFilter)

    def __init__(self, view_model: DeviceListViewModel, integration_store: IntegrationStore, parent=None):
        super().__init__(parent)
        self._view_model = view_model
        self._store = integration_store

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setAnimated(True)
        self.tree.setIndentation(16)
        self.tree.setAcceptDrops(True)
        self.tree.setDragDropMode(QTreeWidget.DropOnly)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.itemClicked.connect(self._on_item_clicked)

        layout.addWidget(self.tree)

        # Build sections
        self._build_sections()

        # Wire up signals
        self._view_model.devices_changed.connect(self._rebuild_sections)
        self._view_model.groups_changed.connect(self._rebuild_sections)

        self.setMinimumWidth(220)

    def _build_sections(self) -> None:
        self.tree.clear()

        # Overview
        overview = QTreeWidgetItem(self.tree, ["Overview"])
        overview.setFlags(overview.flags() & ~Qt.ItemIsSelectable)
        font = overview.font(0)
        font.setBold(True)
        overview.setFont(0, font)

        all_item = DeviceFilterItem("All Devices", DeviceFilter.all(), len(self._view_model.devices))
        self.tree.addTopLevelItem(all_item)

        unresponsive = DeviceFilterItem(
            "Not Responding", DeviceFilter.unresponsive(),
            len(self._view_model.unresponsive_devices())
        )
        self.tree.addTopLevelItem(unresponsive)

        disabled = DeviceFilterItem(
            "Disabled Integrations", DeviceFilter.disabled_integrations(),
            len(self._view_model.devices_from_disabled_integrations())
        )
        self.tree.addTopLevelItem(disabled)

        # Groups
        groups_header = QTreeWidgetItem(self.tree, ["Groups"])
        groups_header.setFlags(groups_header.flags() & ~Qt.ItemIsSelectable)
        groups_header.setFont(0, font)

        for group, members in self._view_model.grouped_by_device_group:
            item = DeviceFilterItem(
                group.name, DeviceFilter.group(group.id), len(members)
            )
            item.setData(0, Qt.UserRole, group)
            item.setFlags(item.flags() | Qt.ItemIsDropEnabled)
            self.tree.addTopLevelItem(item)

        # By Type
        type_header = QTreeWidgetItem(self.tree, ["By Type"])
        type_header.setFlags(type_header.flags() & ~Qt.ItemIsSelectable)
        type_header.setFont(0, font)

        for type_label, devices in self._view_model.grouped_by_type:
            item = DeviceFilterItem(type_label, DeviceFilter.type_(type_label), len(devices))
            self.tree.addTopLevelItem(item)

        # By Integration (Skill)
        skill_header = QTreeWidgetItem(self.tree, ["By Integration (Skill)"])
        skill_header.setFlags(skill_header.flags() & ~Qt.ItemIsSelectable)
        skill_header.setFont(0, font)

        for skill_id, devices in self._view_model.grouped_by_skill:
            label = self._view_model.integration_label(skill_id)
            item = DeviceFilterItem(label, DeviceFilter.skill(skill_id), len(devices))
            self.tree.addTopLevelItem(item)

    def _rebuild_sections(self) -> None:
        self._build_sections()

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        if isinstance(item, DeviceFilterItem):
            self.filter_changed.emit(item.filter_value)

    def _show_context_menu(self, pos) -> None:
        item = self.tree.itemAt(pos)
        if not item or not isinstance(item, DeviceFilterItem):
            return
        fv = item.filter_value
        if fv.kind != "group":
            return
        group = item.data(0, Qt.UserRole)

        menu = QMenu(self)

        rename_action = menu.addAction("Rename...")
        delete_action = menu.addAction("Delete...")

        action = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if action == rename_action:
            new_name, ok = QInputDialog.getText(self, "Rename Group", "Name:", text=group.name)
            if ok and new_name:
                import asyncio
                asyncio.ensure_future(self._view_model.rename_group(group, new_name))
        elif action == delete_action:
            reply = QMessageBox.question(
                self, "Delete Group",
                f'Really delete group "{group.name}"? This cannot be undone.',
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                import asyncio
                asyncio.ensure_future(self._view_model.delete_group(group))

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        item = self.tree.itemAt(event.position().toPoint())
        if not item or not isinstance(item, DeviceFilterItem):
            return
        if item.filter_value.kind != "group":
            return
        group = item.data(0, Qt.UserRole)
        if not group:
            return

        import json
        try:
            data = json.loads(event.mimeData().text())
            appliance_ids: list[str] = data.get("appliance_ids", [])
        except (json.JSONDecodeError, TypeError):
            return

        devices = [d for d in self._view_model.devices if d.appliance_id in appliance_ids]
        if not devices:
            return

        import asyncio
        asyncio.ensure_future(self._view_model.add_devices(devices, to_group=group))
        event.acceptProposedAction()
