import asyncio
import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtCore import Qt, QPoint, QMimeData
from PySide6.QtGui import QDragEnterEvent, QDropEvent

from app.sidebar import Sidebar, DeviceFilterItem
from app.models.filter import DeviceFilter
from app.models.device_group import DeviceGroup


async def async_noop(*args, **kwargs):
    pass


@pytest.fixture
def view_model():
    vm = MagicMock()
    vm.devices = []
    vm.device_groups = []
    vm.is_busy = False
    vm.unresponsive_devices.return_value = []
    vm.grouped_by_device_group = []
    vm.grouped_by_type = []
    vm.grouped_by_skill = []
    return vm


@pytest.fixture
def store():
    store = MagicMock()
    store.meta_for.return_value = MagicMock(display_name=None)
    store.label_for.return_value = "Skill …abc123"
    return store


@pytest.fixture
def sidebar(view_model, store, qtbot):
    sb = Sidebar(view_model, store)
    qtbot.addWidget(sb)
    return sb


class TestDeviceFilterItem:
    def test_create_with_count(self):
        item = DeviceFilterItem("All", DeviceFilter.all(), 5)
        assert item.text(0) == "All (5)"
        assert item.filter_value == DeviceFilter.all()

    def test_create_without_count(self):
        item = DeviceFilterItem("Header", DeviceFilter.all(), -1)
        assert item.text(0) == "Header"

    def test_update_count(self):
        item = DeviceFilterItem("Test", DeviceFilter.all(), 0)
        item.update_count(10)
        assert item.text(0) == "Test (10)"

    def test_update_count_negative(self):
        item = DeviceFilterItem("Test", DeviceFilter.all(), 5)
        item.update_count(-1)
        assert item.text(0) == "Test"


class TestSidebarBuildSections:
    def test_has_overview_items(self, sidebar):
        texts = []
        for i in range(sidebar.tree.topLevelItemCount()):
            texts.append(sidebar.tree.topLevelItem(i).text(0))
        assert "All Devices (0)" in texts
        assert "Not Responding (0)" in texts

    def test_overview_items_have_filters(self, sidebar):
        for i in range(sidebar.tree.topLevelItemCount()):
            item = sidebar.tree.topLevelItem(i)
            if isinstance(item, DeviceFilterItem):
                assert item.filter_value is not None

    def test_headers_not_selectable(self, sidebar):
        for i in range(sidebar.tree.topLevelItemCount()):
            item = sidebar.tree.topLevelItem(i)
            if not isinstance(item, DeviceFilterItem):
                assert not (item.flags() & Qt.ItemIsSelectable)

    def test_groups_section(self, sidebar, view_model):
        group = DeviceGroup(id="g1", name="Living Room", member_endpoint_ids={"id1", "id2"})
        view_model.grouped_by_device_group = [(group, [MagicMock(), MagicMock()])]
        sidebar._rebuild_sections()
        texts = [sidebar.tree.topLevelItem(i).text(0) for i in range(sidebar.tree.topLevelItemCount())]
        assert "Living Room (2)" in texts

    def test_types_section(self, sidebar, view_model):
        view_model.grouped_by_type = [("Light", [MagicMock()]), ("Sensor", [MagicMock()])]
        sidebar._rebuild_sections()
        texts = [sidebar.tree.topLevelItem(i).text(0) for i in range(sidebar.tree.topLevelItemCount())]
        assert "Light (1)" in texts
        assert "Sensor (1)" in texts

    def test_skills_section(self, sidebar, view_model):
        view_model.grouped_by_skill = [("skill1", [MagicMock()]), ("skill2", [MagicMock()])]
        view_model.integration_label.return_value = "My Skill"
        sidebar._rebuild_sections()
        texts = [sidebar.tree.topLevelItem(i).text(0) for i in range(sidebar.tree.topLevelItemCount())]
        assert "My Skill (1)" in texts


class TestSidebarFilterClicks:
    def test_click_all_device(self, sidebar, view_model, qtbot):
        view_model.devices = [MagicMock()]
        sidebar._rebuild_sections()
        all_item = None
        for i in range(sidebar.tree.topLevelItemCount()):
            item = sidebar.tree.topLevelItem(i)
            if item.text(0) == "All Devices (1)":
                all_item = item
                break
        assert all_item is not None
        with qtbot.waitSignal(sidebar.filter_changed, timeout=500) as blocker:
            sidebar._on_item_clicked(all_item, 0)
        assert blocker.args[0] == DeviceFilter.all()

    def test_click_unresponsive(self, sidebar, view_model, qtbot):
        view_model.unresponsive_devices.return_value = [MagicMock()]
        sidebar._rebuild_sections()
        unr_item = None
        for i in range(sidebar.tree.topLevelItemCount()):
            item = sidebar.tree.topLevelItem(i)
            if "Not Responding" in item.text(0):
                unr_item = item
                break
        with qtbot.waitSignal(sidebar.filter_changed, timeout=500) as blocker:
            sidebar._on_item_clicked(unr_item, 0)
        assert blocker.args[0] == DeviceFilter.unresponsive()


class TestSidebarContextMenu:
    def test_context_menu_on_non_group(self, sidebar, qtbot):
        sidebar.show()
        item = sidebar.tree.topLevelItem(0)
        assert not isinstance(item, DeviceFilterItem)
        rect = sidebar.tree.visualItemRect(item)
        with patch("PySide6.QtWidgets.QMenu.exec", return_value=None):
            sidebar._show_context_menu(rect.center())

    def test_context_menu_on_filter_item(self, sidebar, qtbot):
        """Test context menu on a DeviceFilterItem that is not a group.
        Covers sidebar line 129: fv.kind != 'group' -> return."""
        sidebar.show()
        all_item = None
        for i in range(sidebar.tree.topLevelItemCount()):
            item = sidebar.tree.topLevelItem(i)
            if isinstance(item, DeviceFilterItem) and "All Devices" in item.text(0):
                all_item = item
                break
        assert all_item is not None
        assert all_item.filter_value is not None
        assert all_item.filter_value.kind != "group"
        rect = sidebar.tree.visualItemRect(all_item)
        with patch("PySide6.QtWidgets.QMenu.exec", return_value=None):
            # Should not crash and should not create a menu
            sidebar._show_context_menu(rect.center())

    def test_context_menu_rename(self, sidebar, view_model, qtbot):
        group = DeviceGroup(id="g1", name="Old Name", member_endpoint_ids={"id1"})
        view_model.grouped_by_device_group = [(group, [MagicMock()])]
        view_model.rename_group = MagicMock(return_value=async_noop())
        sidebar._rebuild_sections()
        sidebar.resize(300, 400)
        sidebar.show()

        group_item = None
        for i in range(sidebar.tree.topLevelItemCount()):
            item = sidebar.tree.topLevelItem(i)
            if "Old Name" in item.text(0):
                group_item = item
                break
        assert group_item is not None

        sidebar.tree.scrollToItem(group_item)
        rect = sidebar.tree.visualItemRect(group_item)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            with patch.object(sidebar, "_exec_menu") as exec_mock:
                exec_mock.side_effect = lambda menu, pos: [a for a in menu.actions() if a.text() == "Rename..."][0]
                with patch("app.sidebar.QInputDialog.getText", return_value=("New Name", True)):
                    sidebar._show_context_menu(rect.center())
        finally:
            loop.close()
            asyncio.set_event_loop(None)

        view_model.rename_group.assert_called_once()

    def test_context_menu_delete(self, sidebar, view_model, qtbot):
        group = DeviceGroup(id="g1", name="My Group", member_endpoint_ids={"id1"})
        view_model.grouped_by_device_group = [(group, [MagicMock()])]
        view_model.delete_group = MagicMock(return_value=async_noop())
        sidebar._rebuild_sections()
        sidebar.resize(300, 400)
        sidebar.show()

        group_item = None
        for i in range(sidebar.tree.topLevelItemCount()):
            item = sidebar.tree.topLevelItem(i)
            if "My Group" in item.text(0):
                group_item = item
                break
        assert group_item is not None

        sidebar.tree.scrollToItem(group_item)
        rect = sidebar.tree.visualItemRect(group_item)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            with patch.object(sidebar, "_exec_menu") as exec_mock:
                def return_delete_action(menu, pos):
                    for a in menu.actions():
                        if a.text() == "Delete...":
                            return a
                    return None
                exec_mock.side_effect = return_delete_action
                with patch("app.sidebar.QMessageBox.question", return_value=16384):  # QMessageBox.Yes
                    sidebar._show_context_menu(rect.center())
        finally:
            loop.close()
            asyncio.set_event_loop(None)

        view_model.delete_group.assert_called_once()


class TestSidebarDragDrop:
    def test_drag_enter_accepts_text(self, sidebar):
        sidebar.show()
        mime = QMimeData()
        mime.setText("test")
        event = QDragEnterEvent(
            QPoint(0, 0), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier
        )
        sidebar.dragEnterEvent(event)
        assert event.isAccepted()

    def test_drag_enter_ignores_no_text(self, sidebar):
        sidebar.show()
        mime = QMimeData()
        event = QDragEnterEvent(
            QPoint(0, 0), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier
        )
        sidebar.dragEnterEvent(event)
        assert not event.isAccepted()

    def test_drop_on_group(self, sidebar, view_model, qtbot):
        group = DeviceGroup(id="g1", name="Living Room", member_endpoint_ids={})
        dev = MagicMock()
        dev.appliance_id = "a1"
        view_model.grouped_by_device_group = [(group, [dev])]
        view_model.devices = [dev]
        view_model.add_devices = MagicMock(return_value=async_noop())
        sidebar._rebuild_sections()
        sidebar.resize(300, 400)
        sidebar.show()

        group_item = None
        for i in range(sidebar.tree.topLevelItemCount()):
            item = sidebar.tree.topLevelItem(i)
            if "Living Room" in item.text(0):
                group_item = item
                break
        assert group_item is not None

        mime = QMimeData()
        mime.setText('{"appliance_ids": ["a1"]}')
        rect = sidebar.tree.visualItemRect(group_item)
        event = QDropEvent(
            rect.center(), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier
        )
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            sidebar.dropEvent(event)
        finally:
            loop.close()
            asyncio.set_event_loop(None)
        assert event.isAccepted()
        view_model.add_devices.assert_called_once()

    def test_drop_invalid_json(self, sidebar, view_model, qtbot):
        group = DeviceGroup(id="g1", name="Living Room", member_endpoint_ids={})
        view_model.grouped_by_device_group = [(group, [MagicMock()])]
        sidebar._rebuild_sections()
        sidebar.show()

        group_item = None
        for i in range(sidebar.tree.topLevelItemCount()):
            item = sidebar.tree.topLevelItem(i)
            if "Living Room" in item.text(0):
                group_item = item
                break
        assert group_item is not None

        mime = QMimeData()
        mime.setText("not json")
        rect = sidebar.tree.visualItemRect(group_item)
        event = QDropEvent(
            rect.center(), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier
        )
        sidebar.dropEvent(event)
        assert not event.isAccepted()

    def test_drop_non_filter_item(self, sidebar, view_model, qtbot):
        sidebar._rebuild_sections()
        sidebar.show()
        # Drop on empty area outside items - triggers line 162 (not isinstance)
        mime = QMimeData()
        mime.setText('{"appliance_ids": ["a1"]}')
        event = QDropEvent(
            QPoint(5, 5), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier
        )
        sidebar.dropEvent(event)
        assert not event.isAccepted()

    def test_drop_non_group_item(self, sidebar, view_model, qtbot):
        sidebar._rebuild_sections()
        sidebar.show()
        # Drop on "All Devices" item (kind="all", not "group") - triggers line 165
        all_item = None
        for i in range(sidebar.tree.topLevelItemCount()):
            item = sidebar.tree.topLevelItem(i)
            if "All Devices" in item.text(0):
                all_item = item
                break
        assert all_item is not None

        mime = QMimeData()
        mime.setText('{"appliance_ids": ["a1"]}')
        rect = sidebar.tree.visualItemRect(all_item)
        event = QDropEvent(
            rect.center(), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier
        )
        sidebar.dropEvent(event)
        assert not event.isAccepted()

    def test_drop_no_matching_devices(self, sidebar, view_model, qtbot):
        group = DeviceGroup(id="g1", name="Living Room", member_endpoint_ids={})
        view_model.grouped_by_device_group = [(group, [MagicMock()])]
        sidebar._rebuild_sections()
        sidebar.show()

        group_item = None
        for i in range(sidebar.tree.topLevelItemCount()):
            item = sidebar.tree.topLevelItem(i)
            if "Living Room" in item.text(0):
                group_item = item
                break
        assert group_item is not None

        mime = QMimeData()
        mime.setText('{"appliance_ids": ["nonexistent"]}')
        rect = sidebar.tree.visualItemRect(group_item)
        event = QDropEvent(
            rect.center(), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier
        )
        sidebar.dropEvent(event)
        assert not event.isAccepted()

    def test_drop_group_with_no_data(self, sidebar, view_model, qtbot):
        from app.models.filter import DeviceFilter
        sidebar._rebuild_sections()
        sidebar.show()
        # Directly add a DeviceFilterItem with kind="group" but no UserRole data
        item = DeviceFilterItem("Bad Group", DeviceFilter.group("g_none"))
        item.setFlags(item.flags() | Qt.ItemIsDropEnabled)
        sidebar.tree.addTopLevelItem(item)
        sidebar.tree.scrollToItem(item)

        mime = QMimeData()
        mime.setText('{"appliance_ids": ["a1"]}')
        rect = sidebar.tree.visualItemRect(item)
        event = QDropEvent(
            rect.center(), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier
        )
        sidebar.dropEvent(event)
        assert not event.isAccepted()

    def test_exec_menu_calls_menu_exec(self, sidebar, qtbot):
        from PySide6.QtWidgets import QMenu
        from PySide6.QtCore import QPoint
        menu = QMenu(sidebar)
        with patch.object(menu, "exec") as exec_mock:
            exec_mock.return_value = None
            sidebar._exec_menu(menu, QPoint(0, 0))
        exec_mock.assert_called_once()


class TestSidebarRebuild:
    def test_rebuild_updates_counts(self, sidebar, view_model):
        view_model.devices = [MagicMock(), MagicMock()]
        sidebar._rebuild_sections()
        texts = [sidebar.tree.topLevelItem(i).text(0) for i in range(sidebar.tree.topLevelItemCount())]
        assert "All Devices (2)" in texts
