import json

from PySide6.QtCore import QStandardPaths

from app.models.device import Connectivity, Device


def test_backup_devices_writes_recovery_snapshot(view_model, tmp_path, monkeypatch):
    monkeypatch.setattr(QStandardPaths, "writableLocation", lambda _: str(tmp_path))
    device = Device(
        appliance_id="device-1",
        friendly_name="Kitchen Light",
        decoded=None,
        connectivity=Connectivity.UNREACHABLE,
        manufacturer_name="Acme",
        endpoint_id="endpoint-1",
        raw_fields={"custom": "value"},
    )

    path = view_model.backup_devices([device])

    assert path.exists()
    payload = json.loads(path.read_text())
    assert payload == [{
        "applianceId": "device-1",
        "friendlyName": "Kitchen Light",
        "connectivity": "unreachable",
        "manufacturer": "Acme",
        "displayCategory": None,
        "endpointId": "endpoint-1",
        "associatedUnitId": None,
        "rawFields": {"custom": "value"},
    }]
