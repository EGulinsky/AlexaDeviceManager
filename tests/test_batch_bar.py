import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication, QWidget

from app.batch_bar import BatchActionsBar
from app.models.filter import BatchAction
from app.models.device import Device, Connectivity


@pytest.fixture
def view_model():
    vm = MagicMock()
    vm.devices = []
    vm.device_groups = []
    vm.is_busy = False
    vm.unresponsive_devices.return_value = []
    vm.grouped_by_device_group = []
    return vm


@pytest.fixture
def bar(view_model, qtbot):
    b = BatchActionsBar(view_model)
    qtbot.addWidget(b)
    return b


class TestBatchBarInit:
    def test_widget_created(self, bar):
        assert bar.windowTitle() == ""
        assert bar.progress_bar.isVisible() is False
        assert bar.status_label.isVisible() is False

    def test_buttons_exist(self, bar):
        assert bar.delete_sel_btn.text() == "Delete Selected (0)"
        assert bar.delete_unr_btn.text() == "Delete Not Responding (0)"
        assert bar.delete_all_btn.text() == "Delete All (0)"
        assert bar.groups_menu_btn.text() == "Groups (0)"

    def test_buttons_enabled_initially(self, bar):
        assert bar.delete_sel_btn.isEnabled() is True
        assert bar.delete_unr_btn.isEnabled() is True
        assert bar.delete_all_btn.isEnabled() is True


class TestBatchBarUpdateCounts:
    def test_update_with_selection(self, bar, view_model):
        view_model.devices = [Device(appliance_id="d1", friendly_name="D1", decoded=None)]
        view_model.device_groups = []

        bar.update_counts(selected_count=2)
        assert bar.delete_sel_btn.text() == "Delete Selected (2)"
        assert bar.delete_sel_btn.isEnabled() is True
        assert bar.groups_menu_btn.text() == "Groups (2)"
        assert bar.groups_menu_btn.isEnabled() is True

    def test_update_clears_selection(self, bar, view_model):
        bar.update_counts(selected_count=0)
        assert bar.delete_sel_btn.isEnabled() is False
        assert bar.groups_menu_btn.isEnabled() is False

    def test_update_unresponsive_count(self, bar, view_model):
        view_model.unresponsive_devices.return_value = [MagicMock()]
        bar.update_counts(0)
        assert bar.delete_unr_btn.text() == "Delete Not Responding (1)"
        assert bar.delete_unr_btn.isEnabled() is True

    def test_update_all_count(self, bar, view_model):
        view_model.devices = [MagicMock(), MagicMock(), MagicMock()]
        bar.update_counts(0)
        assert bar.delete_all_btn.text() == "Delete All (3)"
        assert bar.delete_all_btn.isEnabled() is True

    def test_update_busy_disables_buttons(self, bar, view_model):
        view_model.devices = [MagicMock()]
        view_model.is_busy = True
        view_model.unresponsive_devices.return_value = [MagicMock()]
        bar.update_counts(1)
        assert bar.delete_sel_btn.isEnabled() is False
        assert bar.delete_all_btn.isEnabled() is False


class TestBatchBarSignals:
    def test_delete_selected_signal(self, bar, qtbot):
        with qtbot.waitSignal(bar.delete_selected, timeout=500):
            bar.delete_sel_btn.click()

    def test_delete_unresponsive_signal(self, bar, qtbot):
        with qtbot.waitSignal(bar.delete_unresponsive, timeout=500):
            bar.delete_unr_btn.click()

    def test_delete_all_signal(self, bar, qtbot):
        with qtbot.waitSignal(bar.delete_all, timeout=500):
            bar.delete_all_btn.click()


class TestBatchBarGroupsMenu:
    def test_groups_menu_no_groups(self, bar):
        menu = bar.groups_menu
        # Should have "Add to Group", "Remove from Group", separator, "New Group from Selection"
        actions = menu.actions()
        assert len(actions) >= 3

        add_menu = actions[0].menu()
        assert add_menu is not None
        assert add_menu.actions()[0].text() == "No groups yet"
        assert add_menu.actions()[0].isEnabled() is False

    def test_groups_menu_with_groups(self, bar, view_model, qtbot):
        group = MagicMock()
        group.name = "Living Room"
        group.id = "g1"
        group.member_endpoint_ids = {"id1"}
        view_model.device_groups = [group]
        view_model.grouped_by_device_group = [(group, [MagicMock()])]
        bar._build_groups_menu([MagicMock()])

        first_action = bar.groups_menu.actions()[0]
        assert first_action.text() == "Add to Group"
        add_menu = first_action.menu()
        qtbot.wait(10)
        add_actions = add_menu.actions()
        assert len(add_actions) == 1
        assert add_actions[0].text() == "Living Room"

    def test_groups_menu_new_group(self, bar, qtbot):
        mock_action = MagicMock()
        mock_action.data.return_value = ("new", None)
        with patch("app.batch_bar.QInputDialog.getText", return_value=("New Group", True)):
            with qtbot.waitSignal(bar.create_group_from_selection, timeout=2000):
                bar._on_groups_menu_action(mock_action)

    def test_groups_menu_add_to_group(self, bar, qtbot):
        group = MagicMock()
        group.name = "Living Room"
        group.id = "g1"
        action = bar.groups_menu.addAction("Living Room")
        action.setData(("add", group))
        with qtbot.waitSignal(bar.add_to_group, timeout=500):
            action.trigger()

    def test_groups_menu_remove_from_group(self, bar, qtbot):
        group = MagicMock()
        group.name = "Living Room"
        group.id = "g1"
        action = bar.groups_menu.addAction("Living Room")
        action.setData(("remove", group))
        with qtbot.waitSignal(bar.remove_from_group, timeout=500):
            action.trigger()

    def test_groups_menu_action_none_data(self, bar):
        mock_action = MagicMock()
        mock_action.data.return_value = None
        bar._on_groups_menu_action(mock_action)


class TestBatchBarStatus:
    def test_on_status_shows_message(self, bar):
        bar.show()
        bar._on_status("Working...")
        assert bar.status_label.text() == "Working..."
        assert bar.status_label.isVisible() is True

    def test_on_status_empty_hides(self, bar):
        bar.show()
        bar._on_status("")
        assert bar.status_label.isVisible() is False

    def test_on_progress_shows_bar(self, bar):
        bar.show()
        bar._on_progress(2, 10)
        assert bar.progress_bar.isVisible() is True
        assert bar.progress_bar.maximum() == 10
        assert bar.progress_bar.value() == 2

    def test_on_progress_clears_bar(self, bar):
        bar.show()
        bar._on_progress(0, 0)
        assert bar.progress_bar.isVisible() is False

    def test_on_progress_zero_total(self, bar):
        bar.show()
        bar._on_progress(5, 0)
        assert bar.progress_bar.isVisible() is False

    def test_on_progress_equal(self, bar):
        bar.show()
        bar._on_progress(10, 10)
        assert bar.progress_bar.isVisible() is True
        assert bar.progress_bar.value() == 10
