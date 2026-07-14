"""Pure parsers for responses returned by Alexa's internal APIs."""

from __future__ import annotations

from typing import Any

from .models.appliance_id import ApplianceIDParser
from .models.device import Connectivity, Device
from .models.device_group import DeviceGroup


def stringify(value: Any) -> str:
    if value is None:
        return "–"
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return ", ".join(stringify(v) for v in value)
    if isinstance(value, dict):
        return ", ".join(f"{k}={stringify(v)}" for k, v in value.items())
    return str(value)


def parse_device(item: dict, known_field_names: set[str]) -> Device:
    friendly_name = item.get("friendlyName", "") or ""
    legacy = item.get("legacyAppliance") or {}
    appliance_id = legacy.get("applianceId", "") or ""
    endpoint_id = item.get("id")

    manufacturer_raw = item.get("manufacturer") or {}
    manufacturer_name = None
    if isinstance(manufacturer_raw, dict):
        value = manufacturer_raw.get("value") or {}
        if isinstance(value, dict):
            manufacturer_name = value.get("text")

    categories = item.get("displayCategories") or {}
    display_category = None
    if isinstance(categories, dict):
        primary = categories.get("primary") or {}
        if isinstance(primary, dict):
            display_category = primary.get("value")

    associated_units = item.get("associatedUnits") or {}
    associated_unit_id = associated_units.get("id") if isinstance(associated_units, dict) else None

    connectivity = Connectivity.UNKNOWN
    features = item.get("features") or []
    if isinstance(features, list):
        feature = next((f for f in features if isinstance(f, dict) and f.get("name") == "connectivity"), None)
        properties = feature.get("properties") or [] if feature else []
        if isinstance(properties, list):
            reachability = next((p for p in properties if isinstance(p, dict) and p.get("__typename") == "Reachability"), None)
            status = reachability.get("reachabilityStatusValue") if reachability else None
            if isinstance(status, str):
                connectivity = {"OK": Connectivity.OK, "UNREACHABLE": Connectivity.UNREACHABLE}.get(status, connectivity)

    raw_fields = {
        key: stringify(value) for key, value in item.items()
        if key not in known_field_names
    }
    return Device(
        appliance_id=appliance_id,
        friendly_name=friendly_name,
        decoded=ApplianceIDParser.decode(appliance_id),
        connectivity=connectivity,
        manufacturer_name=manufacturer_name or None,
        display_category=display_category or None,
        endpoint_id=endpoint_id,
        associated_unit_id=associated_unit_id,
        raw_fields=raw_fields,
    )


def parse_device_group(item: dict) -> DeviceGroup:
    group_id = item.get("id", "") or ""
    name_raw = item.get("friendlyName") or {}
    name = (name_raw.get("value") or {}).get("text") or group_id
    member_items = (item.get("memberDevices") or {}).get("items") or []
    endpoint_ids = {member.get("id", "") for member in member_items if member.get("id")}
    return DeviceGroup(id=group_id, name=name, member_endpoint_ids=endpoint_ids)
