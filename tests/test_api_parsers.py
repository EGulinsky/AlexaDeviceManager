import json
from pathlib import Path

from app.api_parsers import parse_device, parse_device_group, stringify
from app.models.device import Connectivity


def test_stringify_nested_values():
    assert stringify({"enabled": True, "values": [1, None]}) == "enabled=true, values=1, –"


def test_parse_device_extracts_core_fields():
    device = parse_device({
        "id": "endpoint-1",
        "friendlyName": "Kitchen light",
        "legacyAppliance": {"applianceId": "not-encoded"},
        "manufacturer": {"value": {"text": "Acme"}},
        "displayCategories": {"primary": {"value": "LIGHT"}},
        "features": [{"name": "connectivity", "properties": [
            {"__typename": "Reachability", "reachabilityStatusValue": "OK"}
        ]}],
        "custom": {"answer": 42},
    }, {"id", "friendlyName", "legacyAppliance", "manufacturer", "displayCategories", "features"})
    assert device.endpoint_id == "endpoint-1"
    assert device.connectivity is Connectivity.OK
    assert device.manufacturer_name == "Acme"
    assert device.raw_fields == {"custom": "answer=42"}


def test_parse_device_group():
    group = parse_device_group({
        "id": "group-1",
        "friendlyName": {"value": {"text": "Kitchen"}},
        "memberDevices": {"items": [{"id": "e1"}, {"id": "e2"}]},
    })
    assert group.name == "Kitchen"
    assert group.member_endpoint_ids == {"e1", "e2"}


def test_parse_recorded_endpoint_fixture():
    fixture = Path(__file__).parent / "fixtures" / "device_endpoint.json"
    device = parse_device(json.loads(fixture.read_text()), {
        "id", "friendlyName", "legacyAppliance", "manufacturer",
        "displayCategories", "features",
    })
    assert device.friendly_name == "Fixture Light"
    assert device.connectivity is Connectivity.UNREACHABLE
    assert device.raw_fields["customField"] == "source=recorded-fixture"
