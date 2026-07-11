import json
import pytest
from pathlib import Path
from PySide6.QtCore import QObject
from app.store import IntegrationMeta, IntegrationStore


class TestIntegrationMeta:
    def test_default(self):
        m = IntegrationMeta()
        assert m.display_name is None

    def test_with_name(self):
        m = IntegrationMeta("My Skill")
        assert m.display_name == "My Skill"

    def test_to_dict_empty(self):
        m = IntegrationMeta()
        assert m.to_dict() == {}

    def test_to_dict_with_name(self):
        m = IntegrationMeta("My Skill")
        assert m.to_dict() == {"displayName": "My Skill"}

    def test_from_dict_empty(self):
        m = IntegrationMeta.from_dict({})
        assert m.display_name is None

    def test_from_dict_with_name(self):
        m = IntegrationMeta.from_dict({"displayName": "My Skill"})
        assert m.display_name == "My Skill"

    def test_from_dict_extra_keys(self):
        m = IntegrationMeta.from_dict({"displayName": "X", "extra": True})
        assert m.display_name == "X"

    def test_roundtrip(self):
        m1 = IntegrationMeta("Test Name")
        d = m1.to_dict()
        m2 = IntegrationMeta.from_dict(d)
        assert m2.display_name == "Test Name"


class TestIntegrationStoreFile:
    @pytest.fixture
    def temp_store(self, tmp_path, qtbot):
        store = IntegrationStore.__new__(IntegrationStore)
        QObject.__init__(store)
        store._file_path = tmp_path / "integrations.json"
        store._meta = {}
        return store

    def test_meta_for_missing(self, temp_store):
        m = temp_store.meta_for("nonexistent")
        assert m.display_name is None

    def test_meta_for_existing(self, temp_store):
        temp_store._meta["skill1"] = IntegrationMeta("My Skill")
        m = temp_store.meta_for("skill1")
        assert m.display_name == "My Skill"

    def test_label_with_display_name(self, temp_store):
        temp_store._meta["skill1"] = IntegrationMeta("My Skill")
        assert temp_store.label_for("skill1") == "My Skill"

    def test_label_with_dotted_skill(self, temp_store):
        result = temp_store.label_for("amzn1.ask.skill.abc12345")
        assert result == "Skill …abc12345"

    def test_label_without_dot(self, temp_store):
        result = temp_store.label_for("PlainName")
        assert result == "Skill …lainName"

    def test_label_short_skill(self, temp_store):
        result = temp_store.label_for("amzn1.ask.skill.ab")
        assert result == "Skill …ab"

    def test_set_display_name(self, temp_store):
        temp_store.set_display_name("New Name", "skill1")
        assert temp_store._meta["skill1"].display_name == "New Name"

    def test_set_display_name_none(self, temp_store):
        temp_store._meta["skill1"] = IntegrationMeta("Old Name")
        temp_store.set_display_name(None, "skill1")
        assert temp_store._meta["skill1"].display_name is None

    def test_save_and_load(self, tmp_path):
        store = IntegrationStore.__new__(IntegrationStore)
        store._file_path = tmp_path / "integrations.json"
        store._meta = {"s1": IntegrationMeta("Skill A")}
        store._save()
        assert store._file_path.exists()
        data = json.loads(store._file_path.read_text())
        assert data == {"s1": {"displayName": "Skill A"}}

    def test_load_existing(self, tmp_path):
        fp = tmp_path / "integrations.json"
        fp.write_text(json.dumps({"s1": {"displayName": "X"}}))
        store = IntegrationStore.__new__(IntegrationStore)
        store._file_path = fp
        store._load()
        assert store._meta["s1"].display_name == "X"

    def test_load_missing_file(self, tmp_path):
        fp = tmp_path / "integrations.json"
        store = IntegrationStore.__new__(IntegrationStore)
        store._file_path = fp
        store._load()
        assert store._meta == {}

    def test_load_corrupt_json(self, tmp_path):
        fp = tmp_path / "integrations.json"
        fp.write_text("not json")
        store = IntegrationStore.__new__(IntegrationStore)
        store._file_path = fp
        store._load()
        assert store._meta == {}

    def test_label_last_8_chars(self, temp_store):
        skill_id = "amzn1.ask.skill.aVeryLongSkillIdHere"
        label = temp_store.label_for(skill_id)
        assert label == "Skill …llIdHere"
        assert len("Skill …llIdHere") <= 18


class TestIntegrationStoreInit:
    def test_create_with_mocked_path(self, tmp_path, monkeypatch):
        """Test that __init__ creates dir and loads empty state."""
        from PySide6.QtCore import QStandardPaths
        monkeypatch.setattr(
            QStandardPaths, "writableLocation",
            lambda _: str(tmp_path)
        )
        store = IntegrationStore()
        assert store._file_path.parent.exists()
        assert store._meta == {}

    def test_signals(self, tmp_path, monkeypatch):
        from PySide6.QtCore import QStandardPaths
        monkeypatch.setattr(
            QStandardPaths, "writableLocation",
            lambda _: str(tmp_path)
        )
        store = IntegrationStore()
        received = []
        store.meta_changed.connect(lambda: received.append(True))
        store.set_display_name("Name", "s1")
        assert received == [True]
