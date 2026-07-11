import asyncio
import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtCore import Qt, QModelIndex, QPoint
from PySide6.QtWidgets import QApplication, QMenu, QTableView

from app.device_list_view import DeviceTableModel, DeviceFilterProxyModel, DeviceListView
from app.models.device import Device, Connectivity


async def async_noop(*args, **kwargs):
    pass


@pytest.fixture
def devices():
    return [
        Device(appliance_id="a1", friendly_name="Z Device", decoded=None,
               display_category="LIGHT", endpoint_id="e1"),
        Device(appliance_id="a2", friendly_name="A Device", decoded=None,
               display_category="SENSOR", endpoint_id="e2",
               connectivity=Connectivity.UNREACHABLE),
        Device(appliance_id="a3", friendly_name="B Device", decoded=None,
               display_category="CAMERA", endpoint_id="e3",
               raw_fields={"custom": "val"}),
    ]


@pytest.fixture
def view_model(devices):
    vm = MagicMock()
    vm.devices = devices
    vm.integration_label.return_value = "Test Integration"
    vm.grouped_by_device_group = []
    return vm


class TestDeviceTableModel:
    def test_row_count(self, devices, view_model):
        m = DeviceTableModel(devices, view_model)
        assert m.rowCount() == 3

    def test_column_count(self, devices, view_model):
        m = DeviceTableModel(devices, view_model)
        assert m.columnCount() == 6

    def test_column_names(self, devices, view_model):
        m = DeviceTableModel(devices, view_model)
        assert m.COLUMNS == ["Name", "Type", "Integration", "Status", "applianceId", "All Fields"]

    def test_header_data(self, devices, view_model):
        m = DeviceTableModel(devices, view_model)
        assert m.headerData(0, Qt.Horizontal, Qt.DisplayRole) == "Name"
        assert m.headerData(1, Qt.Horizontal, Qt.DisplayRole) == "Type"

    def test_header_data_wrong_orientation(self, devices, view_model):
        m = DeviceTableModel(devices, view_model)
        assert m.headerData(0, Qt.Vertical, Qt.DisplayRole) is None

    def test_data_name_column(self, devices, view_model):
        m = DeviceTableModel(devices, view_model)
        idx = m.index(0, 0)
        assert m.data(idx, Qt.DisplayRole) == "Z Device"

    def test_data_type_column(self, devices, view_model):
        m = DeviceTableModel(devices, view_model)
        idx = m.index(0, 1)
        assert m.data(idx, Qt.DisplayRole) == "Light"

    def test_data_integration_column(self, devices, view_model):
        m = DeviceTableModel(devices, view_model)
        idx = m.index(0, 2)
        assert m.data(idx, Qt.DisplayRole) == "Test Integration"

    def test_data_status_column(self, devices, view_model):
        m = DeviceTableModel(devices, view_model)
        idx = m.index(0, 3)
        assert m.data(idx, Qt.DisplayRole) == "unknown"
        idx2 = m.index(1, 3)
        assert m.data(idx2, Qt.DisplayRole) == "unreachable"

    def test_data_appliance_id_column(self, devices, view_model):
        m = DeviceTableModel(devices, view_model)
        idx = m.index(0, 4)
        assert m.data(idx, Qt.DisplayRole) == "a1"

    def test_data_all_fields_column(self, devices, view_model):
        m = DeviceTableModel(devices, view_model)
        idx = m.index(0, 5)
        assert m.data(idx, Qt.DisplayRole) == "–"
        idx2 = m.index(2, 5)
        assert m.data(idx2, Qt.DisplayRole) == "1 fields"

    def test_data_invalid_index(self, devices, view_model):
        m = DeviceTableModel(devices, view_model)
        assert m.data(QModelIndex(), Qt.DisplayRole) is None

    def test_tooltip_appliance_id(self, devices, view_model):
        m = DeviceTableModel(devices, view_model)
        idx = m.index(0, 4)
        assert m.data(idx, Qt.ToolTipRole) == "a1"

    def test_tooltip_other_column(self, devices, view_model):
        m = DeviceTableModel(devices, view_model)
        idx = m.index(0, 0)
        assert m.data(idx, Qt.ToolTipRole) is None

    def test_device_at_valid(self, devices, view_model):
        m = DeviceTableModel(devices, view_model)
        d = m.device_at(1)
        assert d is not None
        assert d.friendly_name == "A Device"

    def test_device_at_invalid_low(self, devices, view_model):
        m = DeviceTableModel(devices, view_model)
        assert m.device_at(-1) is None

    def test_device_at_invalid_high(self, devices, view_model):
        m = DeviceTableModel(devices, view_model)
        assert m.device_at(100) is None

    def test_set_devices(self, devices, view_model):
        m = DeviceTableModel(devices, view_model)
        m.set_devices([devices[0]])
        assert m.rowCount() == 1

    def test_sort_key_by_name(self, devices, view_model):
        assert DeviceTableModel._sort_key(devices[1], 0) == "a device"

    def test_sort_key_by_type(self, devices, view_model):
        assert DeviceTableModel._sort_key(devices[1], 1) == "sensor"

    def test_sort_key_by_integration(self, devices, view_model):
        assert DeviceTableModel._sort_key(devices[1], 2) == devices[1].integration_group_key

    def test_sort_key_by_status(self, devices, view_model):
        assert DeviceTableModel._sort_key(devices[1], 3) == Connectivity.UNREACHABLE.value

    def test_sort_key_by_appliance_id(self, devices, view_model):
        assert DeviceTableModel._sort_key(devices[1], 4) == "a2"

    def test_sort_key_unknown(self, devices, view_model):
        assert DeviceTableModel._sort_key(devices[1], 99) == ""

    def test_sort_ascending(self, devices, view_model):
        m = DeviceTableModel(devices, view_model)
        m.sort(0, Qt.AscendingOrder)
        assert m._devices[0].friendly_name == "A Device"
        assert m._devices[2].friendly_name == "Z Device"

    def test_sort_descending(self, devices, view_model):
        m = DeviceTableModel(devices, view_model)
        m.sort(0, Qt.DescendingOrder)
        assert m._devices[0].friendly_name == "Z Device"
        assert m._devices[2].friendly_name == "A Device"


class TestDeviceFilterProxyModel:
    def test_accepts_all_without_filter(self, devices, view_model):
        source = DeviceTableModel(devices, view_model)
        proxy = DeviceFilterProxyModel()
        proxy.setSourceModel(source)
        assert proxy.filterAcceptsRow(0, QModelIndex()) is True
        assert proxy.filterAcceptsRow(1, QModelIndex()) is True

    def test_filter_by_name(self, devices, view_model):
        source = DeviceTableModel(devices, view_model)
        proxy = DeviceFilterProxyModel()
        proxy.setSourceModel(source)
        proxy.set_filter_text("Z Device")
        assert proxy.filterAcceptsRow(0, QModelIndex()) is True
        assert proxy.filterAcceptsRow(1, QModelIndex()) is False

    def test_filter_by_appliance_id(self, devices, view_model):
        source = DeviceTableModel(devices, view_model)
        proxy = DeviceFilterProxyModel()
        proxy.setSourceModel(source)
        proxy.set_filter_text("a2")
        assert proxy.filterAcceptsRow(1, QModelIndex()) is True
        assert proxy.filterAcceptsRow(0, QModelIndex()) is False

    def test_filter_case_insensitive(self, devices, view_model):
        source = DeviceTableModel(devices, view_model)
        proxy = DeviceFilterProxyModel()
        proxy.setSourceModel(source)
        proxy.set_filter_text("z device")
        assert proxy.filterAcceptsRow(0, QModelIndex()) is True

    def test_filter_empty_text(self, devices, view_model):
        source = DeviceTableModel(devices, view_model)
        proxy = DeviceFilterProxyModel()
        proxy.setSourceModel(source)
        proxy.set_filter_text("")
        assert all(proxy.filterAcceptsRow(i, QModelIndex()) for i in range(3))

    def test_filter_on_non_model_source(self, view_model):
        proxy = DeviceFilterProxyModel()
        proxy.set_filter_text("anything")
        # The proxy's sourceModel is None by default; filterAcceptsRow returns True
        assert proxy.filterAcceptsRow(0, QModelIndex()) is True

    def test_less_than(self, devices, view_model):
        source = DeviceTableModel(devices, view_model)
        proxy = DeviceFilterProxyModel()
        proxy.setSourceModel(source)
        idx_a = proxy.mapFromSource(source.index(1, 0))
        idx_z = proxy.mapFromSource(source.index(0, 0))
        assert proxy.lessThan(idx_a, idx_z) is True  # "A" < "Z"
        assert proxy.lessThan(idx_z, idx_a) is False


class TestDeviceListView:
    @pytest.fixture
    def list_view(self, devices, view_model, qtbot):
        lv = DeviceListView(view_model)
        qtbot.addWidget(lv)
        return lv

    def test_initial_state(self, list_view):
        list_view.show()
        list_view.set_devices([])
        assert list_view.table.isVisible() is False
        assert list_view.empty_label.isVisible() is True

    def test_set_devices_shows_table(self, list_view, view_model):
        list_view.show()
        list_view.set_devices(view_model.devices)
        assert list_view.table.isVisible() is True
        assert list_view.empty_label.isVisible() is False

    def test_set_devices_empty(self, list_view):
        list_view.show()
        list_view.set_devices([])
        assert list_view.table.isVisible() is False
        assert list_view.empty_label.isVisible() is True

    def test_selected_devices_empty(self, list_view):
        assert list_view.selected_devices() == []

    def test_selected_devices_with_selection(self, list_view, qtbot):
        from PySide6.QtCore import QItemSelectionModel
        list_view.show()
        list_view.set_devices([
            Device(appliance_id="a1", friendly_name="One", decoded=None, endpoint_id="e1"),
            Device(appliance_id="a2", friendly_name="Two", decoded=None, endpoint_id="e2"),
        ])
        src_idx = list_view._model.index(0, 0)
        proxy_idx = list_view._proxy.mapFromSource(src_idx)
        list_view.table.selectionModel().select(
            proxy_idx, QItemSelectionModel.Select | QItemSelectionModel.Rows
        )
        selected = list_view.selected_devices()
        assert len(selected) == 1
        assert selected[0].appliance_id == "a1"

    def test_selection_changed_signal(self, list_view, qtbot):
        list_view.show()
        list_view.set_devices([Device(appliance_id="d1", friendly_name="D1", decoded=None, endpoint_id="e1")])
        with qtbot.waitSignal(list_view.selection_changed, timeout=500):
            list_view.table.selectRow(0)

    def test_model_populated(self, list_view, view_model):
        list_view.set_devices(view_model.devices)
        model = list_view.table.model()
        assert model.rowCount() == len(view_model.devices)

    def test_table_columns(self, list_view, view_model):
        list_view.show()
        list_view.set_devices(view_model.devices)
        header = list_view.table.horizontalHeader()
        assert header.isVisible()

    def test_alternating_row_colors(self, list_view):
        assert list_view.table.alternatingRowColors() is True


class TestDeviceListViewContextMenu:
    @pytest.fixture
    def list_view(self, view_model, qtbot):
        from app.models.device_group import DeviceGroup
        group = DeviceGroup(id="g1", name="Living Room", member_endpoint_ids={"existing_id"})
        view_model.device_groups = [group]
        view_model.grouped_by_device_group = [(group, [MagicMock(), MagicMock()])]
        view_model.add_devices = MagicMock(return_value=async_noop())
        view_model.remove_devices = MagicMock(return_value=async_noop())
        lv = DeviceListView(view_model)
        qtbot.addWidget(lv)
        return lv

    def test_context_menu_shows(self, list_view, qtbot):
        list_view.show()
        list_view.set_devices([
            Device(appliance_id="a1", friendly_name="Z Device", decoded=None, endpoint_id="e1"),
        ])
        list_view.table.resizeColumnsToContents()
        list_view.table.show()
        src_idx = list_view._model.index(0, 0)
        proxy_idx = list_view._proxy.mapFromSource(src_idx)
        rect = list_view.table.visualRect(proxy_idx)
        with patch.object(list_view, "_exec_menu", return_value=None):
            list_view._show_context_menu(rect.center())

    def test_context_menu_outside_item(self, list_view):
        from PySide6.QtCore import QPoint
        with patch.object(list_view, "_exec_menu", return_value=None):
            list_view._show_context_menu(QPoint(-1, -1))
        # No crash for invalid index

    def test_context_menu_device_not_found(self, list_view, qtbot):
        """Test _show_context_menu when device_at returns None (line 180)."""
        list_view.show()
        list_view.set_devices([
            Device(appliance_id="a1", friendly_name="Z Device", decoded=None, endpoint_id="e1"),
        ])
        list_view.table.resizeColumnsToContents()
        list_view.table.show()
        src_idx = list_view._model.index(0, 0)
        proxy_idx = list_view._proxy.mapFromSource(src_idx)
        rect = list_view.table.visualRect(proxy_idx)

        with patch.object(list_view._model, "device_at", return_value=None):
            with patch.object(list_view, "_exec_menu", return_value=None):
                list_view._show_context_menu(rect.center())

    def test_context_menu_add_to_group(self, list_view, qtbot):
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        list_view.show()
        list_view.set_devices([
            Device(appliance_id="a1", friendly_name="Z Device", decoded=None, endpoint_id="e1"),
        ])
        list_view.table.resizeColumnsToContents()
        list_view.table.show()
        src_idx = list_view._model.index(0, 0)
        proxy_idx = list_view._proxy.mapFromSource(src_idx)
        rect = list_view.table.visualRect(proxy_idx)

        with patch.object(list_view, "_exec_menu") as exec_mock:
            def _side_effect(menu, pos):
                groups_menu = menu.actions()[0]
                if groups_menu.menu():
                    action = groups_menu.menu().actions()[0]
                    list_view.__test_keep = (menu, groups_menu, action)
                    return action
                return None
            exec_mock.side_effect = _side_effect
            list_view._show_context_menu(rect.center())

        loop.close()
        list_view._view_model.add_devices.assert_called_once()

    def test_context_menu_remove_from_group(self, list_view, qtbot):
        import asyncio
        from app.models.device_group import DeviceGroup
        group = DeviceGroup(id="g1", name="Living Room", member_endpoint_ids={"e1"})
        list_view._view_model.device_groups = [group]
        list_view._view_model.grouped_by_device_group = [(group, [MagicMock(), MagicMock()])]
        list_view._view_model.add_devices = MagicMock(return_value=async_noop())
        list_view._view_model.remove_devices = MagicMock(return_value=async_noop())
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        list_view.show()
        list_view.set_devices([
            Device(appliance_id="a1", friendly_name="Z Device", decoded=None, endpoint_id="e1"),
        ])
        list_view.table.resizeColumnsToContents()
        list_view.table.show()
        src_idx = list_view._model.index(0, 0)
        proxy_idx = list_view._proxy.mapFromSource(src_idx)
        rect = list_view.table.visualRect(proxy_idx)

        with patch.object(list_view, "_exec_menu") as exec_mock:
            def _side_effect(menu, pos):
                actions = menu.actions()
                for a in actions:
                    if a.menu() and "Remove" in a.text():
                        remove_menu_action = a.menu().actions()[0]
                        list_view.__test_keep = (menu, actions, a, remove_menu_action)
                        return remove_menu_action
                return None
            exec_mock.side_effect = _side_effect
            list_view._show_context_menu(rect.center())

        loop.close()
        list_view._view_model.remove_devices.assert_called_once()

    def test_exec_menu_calls_menu_exec(self, list_view, qtbot):
        from PySide6.QtWidgets import QMenu
        from PySide6.QtCore import QPoint
        from unittest.mock import MagicMock
        menu = QMenu(list_view)
        with patch.object(menu, "exec") as exec_mock:
            exec_mock.return_value = None
            list_view._exec_menu(menu, QPoint(0, 0))
        exec_mock.assert_called_once()
