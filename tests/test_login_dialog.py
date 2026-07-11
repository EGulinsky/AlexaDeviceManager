import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from PySide6.QtCore import Qt

from app.session import AlexaSession
from app.login_dialog import LoginDialog


@pytest.fixture
def session(qtbot):
    from PySide6.QtWidgets import QWidget
    session = MagicMock(spec=AlexaSession)
    session.is_logged_in = MagicMock()
    session.is_loading = MagicMock()
    session.last_error = MagicMock()
    session.current_url = MagicMock()
    session.logged_in = False
    session.region = MagicMock()
    session.region.label = "Europe (Germany)"
    session.region.base_url = "https://alexa.amazon.de"
    session.web_view = QWidget()
    return session


@pytest.fixture
def dialog(session, qtbot):
    dlg = LoginDialog(session)
    qtbot.addWidget(dlg)
    return dlg


class TestLoginDialogInit:
    def test_title(self, dialog):
        assert dialog.windowTitle() == "Sign in to Amazon"

    def test_minimum_size(self, dialog):
        assert dialog.minimumSize().width() >= 800
        assert dialog.minimumSize().height() >= 700

    def test_initial_status(self, dialog):
        assert dialog.status_label.text() == "Not Signed In"
        assert dialog.status_label.styleSheet() == "color: gray;"

    def test_buttons_exist(self, dialog):
        assert dialog.sign_in_btn.text() == "1. Sign in with Amazon"
        assert dialog.load_alexa_btn.text() == "2. Load Alexa"
        assert dialog.check_btn.text() == "Check Sign-In"
        assert dialog.done_btn.text() == "Done"

    def test_region_combo_populated(self, dialog):
        assert dialog.region_combo.count() > 0

    def test_calls_load_sign_in(self, session):
        session.logged_in = False
        dlg = LoginDialog(session)
        session.load_sign_in_page.assert_called_once()


class TestLoginDialogButtons:
    def test_sign_in_button(self, session, qtbot):
        dlg = LoginDialog(session)
        qtbot.addWidget(dlg)
        dlg.sign_in_btn.click()
        session.load_sign_in_page.assert_called()

    def test_load_alexa_button(self, session, qtbot):
        dlg = LoginDialog(session)
        qtbot.addWidget(dlg)
        dlg.load_alexa_btn.click()
        session.load_alexa_host.assert_called()

    def test_check_button(self, session, qtbot):
        dlg = LoginDialog(session)
        qtbot.addWidget(dlg)
        with patch("app.login_dialog.asyncio.ensure_future") as mock_ensure:
            dlg.check_btn.click()
            mock_ensure.assert_called_once()

    def test_done_button(self, session, qtbot):
        dlg = LoginDialog(session)
        qtbot.addWidget(dlg)
        dlg.done_btn.click()
        assert dlg.result() == 1  # QDialog.Accepted


class TestLoginDialogSignals:
    def test_on_login_changed_signed_in(self, session, qtbot):
        dlg = LoginDialog(session)
        qtbot.addWidget(dlg)
        dlg._on_login_changed(True)
        assert dlg.status_label.text() == "Signed In"
        assert dlg.status_label.styleSheet() == "color: green;"

    def test_on_login_changed_signed_out(self, session, qtbot):
        dlg = LoginDialog(session)
        qtbot.addWidget(dlg)
        dlg._on_login_changed(False)
        assert dlg.status_label.text() == "Not Signed In"
        assert dlg.status_label.styleSheet() == "color: gray;"

    def test_on_loading_disables_buttons(self, session, qtbot):
        dlg = LoginDialog(session)
        qtbot.addWidget(dlg)
        dlg._on_loading(True)
        assert dlg.sign_in_btn.isEnabled() is False
        assert dlg.load_alexa_btn.isEnabled() is False
        assert dlg.check_btn.isEnabled() is False

    def test_on_loading_enables_buttons(self, session, qtbot):
        dlg = LoginDialog(session)
        qtbot.addWidget(dlg)
        dlg._on_loading(False)
        assert dlg.sign_in_btn.isEnabled() is True
        assert dlg.load_alexa_btn.isEnabled() is True
        assert dlg.check_btn.isEnabled() is True

    def test_on_error_without_hint(self, session, qtbot):
        dlg = LoginDialog(session)
        qtbot.addWidget(dlg)
        dlg._on_error("Some error")
        assert "Some error" in dlg.error_label.text()

    def test_on_error_with_timeout_hint(self, session, qtbot):
        dlg = LoginDialog(session)
        qtbot.addWidget(dlg)
        dlg._on_error("timed out")
        assert "timed out" in dlg.error_label.text()
        assert "redirected" in dlg.error_label.text()

    def test_on_error_with_http_error_hint(self, session, qtbot):
        dlg = LoginDialog(session)
        qtbot.addWidget(dlg)
        dlg._on_error("http error -1")
        assert "Could not reach the API" in dlg.error_label.text()

    def test_on_error_with_http_status_hint(self, session, qtbot):
        dlg = LoginDialog(session)
        qtbot.addWidget(dlg)
        dlg._on_error("http error 500")
        assert "sign in again" in dlg.error_label.text()

    def test_on_url(self, session, qtbot):
        dlg = LoginDialog(session)
        qtbot.addWidget(dlg)
        dlg._on_url("https://example.com")
        assert dlg.url_label.text() == "Current URL: https://example.com"


class TestLoginDialogRegion:
    def test_region_change(self, session, qtbot):
        dlg = LoginDialog(session)
        qtbot.addWidget(dlg)
        # Switch to last region
        last_idx = dlg.region_combo.count() - 1
        dlg.region_combo.setCurrentIndex(last_idx)
        new_region = dlg.region_combo.itemData(last_idx)
        assert session.region == new_region


class TestLoginDialogDone:
    def test_done_hides_web_view(self, dialog):
        from unittest.mock import patch
        with patch.object(dialog.session.web_view, "setParent") as mock_set_parent:
            with patch.object(dialog.session.web_view, "hide") as mock_hide:
                dialog.done(0)
                mock_set_parent.assert_called_once_with(None)
                mock_hide.assert_called_once()
