from __future__ import annotations
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox,
    QLabel, QProgressBar,
)
from PySide6.QtCore import Qt

from .session import AlexaSession
from .models.region import AlexaRegion


class LoginDialog(QDialog):
    def __init__(self, session: AlexaSession, parent=None):
        super().__init__(parent)
        self.session = session
        self.setWindowTitle("Sign in to Amazon")
        self.setMinimumSize(800, 700)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 8, 8, 8)

        self.region_combo = QComboBox()
        for r in AlexaRegion.candidates:
            self.region_combo.addItem(r.label, r)
        self.region_combo.currentIndexChanged.connect(self._on_region_changed)
        toolbar.addWidget(QLabel("Region:"))
        toolbar.addWidget(self.region_combo)

        self.sign_in_btn = QPushButton("1. Sign in with Amazon")
        self.sign_in_btn.clicked.connect(self.session.load_sign_in_page)
        toolbar.addWidget(self.sign_in_btn)

        self.load_alexa_btn = QPushButton("2. Load Alexa")
        self.load_alexa_btn.clicked.connect(self.session.load_alexa_host)
        toolbar.addWidget(self.load_alexa_btn)

        self.check_btn = QPushButton("Check Sign-In")
        self.check_btn.clicked.connect(self._check_login)
        toolbar.addWidget(self.check_btn)

        toolbar.addStretch()

        self.status_label = QLabel("Not Signed In")
        self.status_label.setStyleSheet("color: gray;")
        toolbar.addWidget(self.status_label)

        self.done_btn = QPushButton("Done")
        self.done_btn.clicked.connect(self.accept)
        toolbar.addWidget(self.done_btn)

        layout.addLayout(toolbar)

        # Info text
        info = QLabel(
            'First use "Sign in with Amazon" — this opens the Amazon homepage. '
            "Click \"Sign in\" in the top right there and log in normally with "
            "email/password (+ 2FA). Then tap \"Load Alexa\" to pick up the session. "
            "If Check Sign-In fails, make sure the URL below starts with "
            "\"alexa.amazon.\" (or your region's Alexa domain) — "
            "if not, try a different region."
        )
        info.setStyleSheet("color: gray; font-size: 11px; padding: 0 8px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        # URL display
        self.url_label = QLabel()
        self.url_label.setStyleSheet("color: gray; font-size: 10px; padding: 0 8px 8px;")
        self.url_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.url_label)

        # Error
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: red; font-size: 11px; padding: 0 8px 4px;")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        # WebView
        layout.addWidget(self.session.web_view, 1)

        # Connections
        self.session.is_logged_in.connect(self._on_login_changed)
        self.session.is_loading.connect(self._on_loading)
        self.session.last_error.connect(self._on_error)
        self.session.current_url.connect(self._on_url)

        # Initial load
        if not self.session.logged_in:
            self.session.load_sign_in_page()

    def _on_region_changed(self, index: int) -> None:
        region: AlexaRegion = self.region_combo.currentData()
        self.session.region = region

    def _check_login(self) -> None:
        import asyncio
        asyncio.ensure_future(self.session.check_login_status())

    def _on_login_changed(self, logged_in: bool) -> None:
        if logged_in:
            self.status_label.setText("Signed In")
            self.status_label.setStyleSheet("color: green;")
        else:
            self.status_label.setText("Not Signed In")
            self.status_label.setStyleSheet("color: gray;")

    def _on_loading(self, loading: bool) -> None:
        self.sign_in_btn.setEnabled(not loading)
        self.load_alexa_btn.setEnabled(not loading)
        self.check_btn.setEnabled(not loading)

    def _on_error(self, err: str) -> None:
        if err:
            hint = ""
            if "timed out" in err.lower():
                hint = " The page may have redirected. Try a different region, or load the Alexa host again."
            elif "http error -1" in err.lower():
                hint = " Could not reach the API. Check your network and the current URL."
            elif "http error" in err.lower():
                hint = " The API returned an error. You may need to sign in again."
            self.error_label.setText(err + hint)

    def _on_url(self, url: str) -> None:
        self.url_label.setText(f"Current URL: {url}")

    def done(self, result: int) -> None:
        self.session.web_view.setParent(None)
        self.session.web_view.hide()
        super().done(result)
