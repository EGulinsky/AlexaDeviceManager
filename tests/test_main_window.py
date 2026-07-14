import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from PySide6.QtWidgets import QMessageBox

from app.main_window import MainWindow
from app.models.filter import DeviceFilter, BatchAction


@pytest.fixture
def session():
    from PySide6.QtWidgets import QWidget
    s = MagicMock()
    s.logged_in = False
    s.is_logged_in = MagicMock()
    s.is_loading = MagicMock()
    s.last_error = MagicMock()
    s.current_url = MagicMock()
    s.attempt_auto_login = AsyncMock(return_value=False)
    s.fetch_devices = AsyncMock(return_value=[])
    s.fetch_device_groups = AsyncMock(return_value=[])
    s.fetch_all_endpoint_field_names = AsyncMock(return_value="available fields")
    s.web_view = QWidget()
    return s


@pytest.fixture
def store():
    s = MagicMock()
    return s


@pytest.fixture
def window(session, store, qtbot, monkeypatch):
    monkeypatch.setattr("app.main_window.AlexaSession", lambda: session)
    monkeypatch.setattr("app.main_window.IntegrationStore", lambda: store)
    w = MainWindow()
    qtbot.addWidget(w)
    return w


class TestMainWindowInit:
    def test_title_contains_version(self, window):
        from app._version import VERSION
        assert VERSION in window.windowTitle()

    def test_minimum_size(self, window):
        assert window.minimumSize().width() == 900
        assert window.minimumSize().height() == 600

    def test_components_exist(self, window):
        assert window.session is not None
        assert window.store is not None
        assert window.view_model is not None
        assert window.sidebar is not None
        assert window.device_list is not None
        assert window.batch_bar is not None

    def test_toolbar_actions(self, window):
        assert window.sign_in_action.text() == "Sign in"
        assert window.refresh_action.text() == "Refresh"
        assert window.fields_action.text() == "Check Fields"
        assert window.refresh_action.isEnabled() is False
        assert window.fields_action.isEnabled() is False


class TestMainWindowLogin:
    def test_login_changed_signed_in(self, window):
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        window._on_login_changed(True)
        loop.close()
        assert window.sign_in_action.text() == "Signed in"
        assert window.refresh_action.isEnabled() is True
        assert window.fields_action.isEnabled() is True

    def test_login_changed_signed_out(self, window):
        window._on_login_changed(False)
        assert window.sign_in_action.text() == "Sign in"
        assert window.refresh_action.isEnabled() is False
        assert window.fields_action.isEnabled() is False

    def test_show_login_opens_dialog(self, window):
        window._show_login()
        assert window._login_dialog is not None
        assert window._login_dialog.isVisible() is True

    def test_show_login_raises_existing(self, window):
        window._show_login()
        first = window._login_dialog
        window._show_login()
        assert window._login_dialog is first


class TestMainWindowFilter:
    def test_filter_all(self, window):
        window._on_filter_changed(DeviceFilter.all())
        assert window.device_list.table.isVisible() is False

    def test_filter_skill(self, window):
        window.view_model._devices = [
            MagicMock(integration_group_key="skill1", type_label="Light"),
            MagicMock(integration_group_key="skill2", type_label="Sensor"),
        ]
        window._on_filter_changed(DeviceFilter.skill("skill1"))
        assert window.device_list._model.rowCount() == 1

    def test_filter_type(self, window):
        window.view_model._devices = [
            MagicMock(integration_group_key="s1", type_label="Light"),
            MagicMock(integration_group_key="s2", type_label="Sensor"),
        ]
        window._on_filter_changed(DeviceFilter.type_("Light"))
        assert window.device_list._model.rowCount() == 1

    def test_filter_group(self, window):
        window.view_model.devices_in_group = MagicMock(return_value=[MagicMock()])
        window._on_filter_changed(DeviceFilter.group("g1"))
        window.view_model.devices_in_group.assert_called_with("g1")

    def test_filter_unresponsive(self, window):
        window.view_model.unresponsive_devices = MagicMock(return_value=[MagicMock()])
        window._on_filter_changed(DeviceFilter.unresponsive())
        window.view_model.unresponsive_devices.assert_called_once()

    def test_filter_unknown_kind_falls_back(self, window):
        window._on_filter_changed(DeviceFilter("unknown_kind"))
        # Falls back to showing all devices (empty list by default)


class TestMainWindowDevicesChanged:
    def test_on_devices_changed(self, window):
        from app.models.device import Device
        d = Device(appliance_id="d1", friendly_name="D1", decoded=None, endpoint_id="e1")
        window.view_model._devices = [d]
        window.device_list.set_devices = MagicMock()
        window.device_list.selected_devices = MagicMock(return_value=[d])
        window.batch_bar.update_counts = MagicMock()
        window._on_devices_changed()
        window.device_list.set_devices.assert_called_once_with([d])
        window.batch_bar.update_counts.assert_called_once_with(1)

    def test_on_groups_changed(self, window):
        window.device_list.selected_devices = MagicMock(return_value=[])
        window.batch_bar.update_counts = MagicMock()
        window._on_groups_changed()
        window.batch_bar.update_counts.assert_called_once_with(0)

    def test_on_login_finished_clears_dialog(self, window):
        window._login_dialog = MagicMock()
        window._on_login_finished(0)
        assert window._login_dialog is None

    def test_confirm_batch_delete_empty_devices(self, window):
        window._target_devices = MagicMock(return_value=[])
        window._confirm_batch_delete(BatchAction("selected", []))


class TestMainWindowBatch:
    @pytest.fixture
    def window_with_selection(self, window):
        from app.models.device import Device
        devices = [Device(appliance_id="d1", friendly_name="D1", decoded=None, endpoint_id="e1")]
        window.view_model._devices = devices
        window.device_list.set_devices(devices)
        window.device_list.table.selectRow(0)
        return window

    def test_delete_selected(self, window_with_selection):
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        w = window_with_selection
        with patch("app.main_window.QMessageBox.question", return_value=QMessageBox.Yes):
            w._delete_selected()
        loop.close()

    def test_delete_unresponsive(self, window):
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        window.view_model.unresponsive_devices = MagicMock(return_value=[MagicMock()])
        with patch("app.main_window.QMessageBox.question", return_value=QMessageBox.Yes):
            window._delete_unresponsive()
        loop.close()

    def test_delete_all(self, window):
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        window.view_model._devices = [MagicMock()]
        with patch("app.main_window.QMessageBox.question", return_value=QMessageBox.Yes):
            window._delete_all()
        loop.close()

    def test_target_devices_selected(self, window_with_selection):
        result = window_with_selection._target_devices(BatchAction("selected", []))
        assert len(result) == 1

    def test_target_devices_unresponsive(self, window):
        window.view_model.unresponsive_devices = MagicMock(return_value=[MagicMock()])
        result = window._target_devices(BatchAction.unresponsive())
        assert len(result) == 1

    def test_target_devices_all(self, window):
        window.view_model._devices = [MagicMock(), MagicMock()]
        result = window._target_devices(BatchAction.all())
        assert len(result) == 2

    def test_target_devices_custom(self, window):
        result = window._target_devices(BatchAction("custom", [MagicMock()]))
        assert len(result) == 1


class TestMainWindowAsyncSlots:
    @pytest.mark.asyncio
    async def test_refresh(self, window):
        window.view_model.refresh = AsyncMock()
        await window._refresh()
        window.view_model.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_add_to_group(self, window):
        window.view_model.add_devices = AsyncMock()
        window.device_list.selected_devices = MagicMock(return_value=[MagicMock()])
        group = MagicMock()
        await window._add_to_group("g1", group)
        window.view_model.add_devices.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_remove_from_group(self, window):
        window.view_model.remove_devices = AsyncMock()
        window.device_list.selected_devices = MagicMock(return_value=[MagicMock()])
        group = MagicMock()
        await window._remove_from_group("g1", group)
        window.view_model.remove_devices.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_group_from_selection(self, window):
        window.view_model.create_group = AsyncMock()
        window.device_list.selected_devices = MagicMock(return_value=[MagicMock()])
        await window._create_group_from_selection("New Group")
        window.view_model.create_group.assert_awaited_once_with(name="New Group", members=window.device_list.selected_devices())

    @pytest.mark.asyncio
    async def test_start(self, window):
        window._auto_login = AsyncMock()
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        window.start()
        loop.close()

    @pytest.mark.asyncio
    async def test_auto_login_success(self, window, session):
        session.attempt_auto_login = AsyncMock(return_value=True)
        window.view_model.refresh = AsyncMock()
        await window._auto_login()
        session.attempt_auto_login.assert_awaited_once()
        window.view_model.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_auto_login_failure(self, window, session):
        session.attempt_auto_login = AsyncMock(return_value=False)
        window._show_login = MagicMock()
        await window._auto_login()
        session.attempt_auto_login.assert_awaited_once()
        window._show_login.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_fields_success(self, window, session):
        session.fetch_all_endpoint_field_names = AsyncMock(return_value="fields")
        with patch("app.main_window.QMessageBox.information") as info:
            await window._check_fields()
            info.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_fields_failure(self, window, session):
        session.fetch_all_endpoint_field_names = AsyncMock(side_effect=Exception("fail"))
        with patch("app.main_window.QMessageBox.warning") as warn:
            await window._check_fields()
            warn.assert_called_once()


class TestMainWindowAbout:
    def test_about_dialog(self, window):
        shown = []
        with patch.object(QMessageBox, "exec", return_value=None):
            window._show_about()

    def test_about_with_git_log(self, window):
        def fake_run(*a, **kw):
            m = MagicMock()
            m.stdout = "commit abc123\n"
            return m
        with patch("app.main_window.subprocess.run", fake_run):
            with patch.object(QMessageBox, "exec", return_value=None):
                window._show_about()

    def test_about_without_git(self, window):
        with patch("app.main_window.subprocess.run", side_effect=Exception("no git")):
            with patch.object(QMessageBox, "exec", return_value=None):
                window._show_about()


class TestMainWindowBusy:
    def test_on_busy_with_login(self, window):
        window.session.is_logged_in = True
        window._on_busy(True)
        assert window.refresh_action.isEnabled() is False

    def test_on_busy_not_busy(self, window):
        window.session.is_logged_in = True
        window._on_busy(False)
        assert window.refresh_action.isEnabled() is True

    def test_on_busy_not_logged_in(self, window):
        window.session.is_logged_in = False
        window._on_busy(False)
        assert window.refresh_action.isEnabled() is False


class TestMainEntrypoint:
    def test_main_runs(self):
        from unittest.mock import patch, MagicMock

        mock_app = MagicMock()
        mock_window = MagicMock()
        mock_loop = MagicMock()
        mock_loop.__enter__ = MagicMock(return_value=mock_loop)
        mock_loop.__exit__ = MagicMock(return_value=None)

        with patch("app.main.QApplication", return_value=mock_app):
            with patch("app.main.QEventLoop", return_value=mock_loop):
                with patch("app.main.MainWindow", return_value=mock_window):
                    with patch("app.main.asyncio.set_event_loop"):
                        from app.main import main
                        main()

        mock_app.setApplicationName.assert_called_once_with("AlexaDeviceManager")
        mock_app.setOrganizationName.assert_called_once_with("AlexaDeviceManager")
        mock_window.start.assert_called_once()
        mock_window.show.assert_called_once()
        mock_loop.run_forever.assert_called_once()

    def test_name_main_guard(self):
        import ast
        import os

        source_path = os.path.join(os.path.dirname(__file__), os.pardir, "app", "main.py")
        with open(source_path) as f:
            tree = ast.parse(f.read())
        guard = tree.body[-1]
        assert isinstance(guard, ast.If)
        code = compile(ast.Module(body=[guard], type_ignores=[]), source_path, "exec")
        mock_main = MagicMock()
        exec(code, {"__name__": "__main__", "main": mock_main})
        mock_main.assert_called_once()
