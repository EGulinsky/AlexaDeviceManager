from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableView, QHeaderView, QMenu,
    QLabel, QPushButton, QHBoxLayout,
)
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, Signal, Slot, QSortFilterProxyModel
from PySide6.QtGui import QDrag, QPixmap, QPainter, QColor, QFont

from .models.device import Device, Connectivity
from .models.device_group import DeviceGroup
from .view_model import DeviceListViewModel


class DeviceTableModel(QAbstractTableModel):
    COLUMNS = ["Name", "Type", "Integration", "Status", "applianceId", "All Fields"]

    def __init__(self, devices: list[Device], view_model: DeviceListViewModel, parent=None):
        super().__init__(parent)
        self._devices = devices
        self._view_model = view_model

    def set_devices(self, devices: list[Device]) -> None:
        self.beginResetModel()
        self._devices = devices
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._devices)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.COLUMNS)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        device = self._devices[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return device.friendly_name
            elif col == 1:
                return device.type_label
            elif col == 2:
                return self._view_model.integration_label(device.integration_group_key)
            elif col == 3:
                return device.connectivity.value
            elif col == 4:
                return device.appliance_id
            elif col == 5:
                return f"{len(device.raw_fields)} fields" if device.raw_fields else "–"
        elif role == Qt.ItemDataRole.DecorationRole:
            if col == 1:
                pass
        elif role == Qt.ItemDataRole.ToolTipRole:
            if col == 4:
                return device.appliance_id

        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.COLUMNS[section]
        return None

    def device_at(self, row: int) -> Device | None:
        if 0 <= row < len(self._devices):
            return self._devices[row]
        return None

    def sort(self, column: int, order: Qt.SortOrder = Qt.AscendingOrder) -> None:
        self.beginResetModel()
        reverse = order == Qt.DescendingOrder
        col_key = column
        self._devices.sort(key=lambda d: self._sort_key(d, col_key), reverse=reverse)
        self.endResetModel()

    @staticmethod
    def _sort_key(device: Device, column: int) -> str:
        if column == 0:
            return device.friendly_name.lower()
        elif column == 1:
            return device.type_label.lower()
        elif column == 2:
            return device.integration_group_key.lower()
        elif column == 3:
            return device.connectivity.value
        elif column == 4:
            return device.appliance_id
        return ""


class DeviceFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._filter_text = ""

    def set_filter_text(self, text: str) -> None:
        self._filter_text = text.lower()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if not self._filter_text:
            return True
        model = self.sourceModel()
        if not isinstance(model, DeviceTableModel):
            return True
        device = model._devices[source_row]
        return (self._filter_text in device.friendly_name.lower()
                or self._filter_text in device.appliance_id.lower())

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        lv = self.sourceModel().data(left, Qt.ItemDataRole.DisplayRole) or ""
        rv = self.sourceModel().data(right, Qt.ItemDataRole.DisplayRole) or ""
        return lv.lower() < rv.lower()


class DeviceListView(QWidget):
    selection_changed = Signal()

    def __init__(self, view_model: DeviceListViewModel, parent=None):
        super().__init__(parent)
        self._view_model = view_model
        self._model = DeviceTableModel(view_model.devices, view_model)
        self._proxy = DeviceFilterProxyModel()
        self._proxy.setSourceModel(self._model)
        self._proxy.setSortRole(Qt.ItemDataRole.DisplayRole)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableView()
        self.table.setModel(self._proxy)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().hide()
        self.table.setDragEnabled(True)
        self.table.setAcceptDrops(False)
        self.table.setDragDropMode(QTableView.DragOnly)
        self.table.setDropIndicatorShown(True)

        self.empty_label = QLabel("No Devices\nSign in and tap \"Refresh\" to load devices.")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("color: gray; font-size: 14px;")

        self.stack = QWidget()
        stack_layout = QVBoxLayout(self.stack)
        stack_layout.addWidget(self.table)
        stack_layout.addWidget(self.empty_label)

        layout.addWidget(self.stack)

        self.table.selectionModel().selectionChanged.connect(lambda: self.selection_changed.emit())

    def set_devices(self, devices: list[Device]) -> None:
        self._model.set_devices(devices)
        has_devices = len(devices) > 0
        self.table.setVisible(has_devices)
        self.empty_label.setVisible(not has_devices)

    def selected_devices(self) -> list[Device]:
        rows = set()
        for index in self.table.selectionModel().selectedRows():
            source = self._proxy.mapToSource(index)
            rows.add(source.row())
        return [self._model._devices[r] for r in sorted(rows)]

    def _show_context_menu(self, pos) -> None:
        index = self.table.indexAt(pos)
        if not index.isValid():
            return
        source = self._proxy.mapToSource(index)
        device = self._model.device_at(source.row())
        if not device:
            return

        menu = QMenu(self)

        groups_menu = menu.addMenu("Add to Group")
        for g, _ in self._view_model.grouped_by_device_group:
            if device.endpoint_id and device.endpoint_id not in g.member_endpoint_ids:
                action = groups_menu.addAction(g.name)
                action.setData(g.id)
        if not groups_menu.actions():
            groups_menu.addAction("No other groups").setEnabled(False)

        remove_menu = menu.addMenu("Remove from Group")
        for g, _ in self._view_model.grouped_by_device_group:
            if device.endpoint_id and device.endpoint_id in g.member_endpoint_ids:
                action = remove_menu.addAction(g.name)
                action.setData(g.id)
        if not remove_menu.actions():
            remove_menu.addAction("Not in any group").setEnabled(False)

        action = self._exec_menu(menu, pos)
        if action and action.parent() == groups_menu:
            group_id = action.data()
            group = next((g for g in self._view_model.device_groups if g.id == group_id), None)
            if group:
                import asyncio
                asyncio.ensure_future(self._view_model.add_devices([device], to_group=group))
        elif action and action.parent() == remove_menu:
            group_id = action.data()
            group = next((g for g in self._view_model.device_groups if g.id == group_id), None)
            if group:
                import asyncio
                asyncio.ensure_future(self._view_model.remove_devices([device], from_group=group))

    def _exec_menu(self, menu, pos):
        return menu.exec(self.table.viewport().mapToGlobal(pos))
