from __future__ import annotations
import json
from pathlib import Path
from PySide6.QtCore import QObject, Signal
from PySide6.QtCore import QStandardPaths


class IntegrationMeta:
    def __init__(self, display_name: str | None = None):
        self.display_name = display_name

    def to_dict(self) -> dict:
        d: dict = {}
        if self.display_name is not None:
            d["displayName"] = self.display_name
        return d

    @staticmethod
    def from_dict(d: dict) -> IntegrationMeta:
        return IntegrationMeta(display_name=d.get("displayName"))


class IntegrationStore(QObject):
    meta_changed = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        data_dir = Path(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation))
        app_dir = data_dir / "AlexaDeviceManager"
        app_dir.mkdir(parents=True, exist_ok=True)
        self._file_path = app_dir / "integrations.json"
        self._meta: dict[str, IntegrationMeta] = {}
        self._load()

    def meta_for(self, skill_id: str) -> IntegrationMeta:
        return self._meta.get(skill_id, IntegrationMeta())

    def label_for(self, skill_id: str) -> str:
        m = self.meta_for(skill_id)
        if m.display_name:
            return m.display_name
        last_component = skill_id.split(".")[-1] if "." in skill_id else skill_id
        return f"Skill …{last_component[-8:]}"

    def set_display_name(self, name: str | None, skill_id: str) -> None:
        m = self.meta_for(skill_id)
        m.display_name = name if name else None
        self._meta[skill_id] = m
        self._save()
        self.meta_changed.emit()

    def _load(self) -> None:
        try:
            data = json.loads(self._file_path.read_text())
            self._meta = {k: IntegrationMeta.from_dict(v) for k, v in data.items()}
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            self._meta = {}

    def _save(self) -> None:
        data = {k: v.to_dict() for k, v in self._meta.items()}
        self._file_path.write_text(json.dumps(data, indent=2))
