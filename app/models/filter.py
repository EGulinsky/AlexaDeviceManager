from __future__ import annotations
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .device import Device


class DeviceFilter:
    def __init__(self, kind: str, value: str | None = None):
        self.kind = kind
        self.value = value

    @staticmethod
    def all() -> DeviceFilter:
        return DeviceFilter("all")

    @staticmethod
    def skill(skill_id: str) -> DeviceFilter:
        return DeviceFilter("skill", skill_id)

    @staticmethod
    def type_(type_label: str) -> DeviceFilter:
        return DeviceFilter("type", type_label)

    @staticmethod
    def group(group_id: str) -> DeviceFilter:
        return DeviceFilter("group", group_id)

    @staticmethod
    def unresponsive() -> DeviceFilter:
        return DeviceFilter("unresponsive")

    @staticmethod
    def disabled_integrations() -> DeviceFilter:
        return DeviceFilter("disabledIntegrations")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DeviceFilter):
            return NotImplemented
        return self.kind == other.kind and self.value == other.value

    def __hash__(self) -> int:
        return hash((self.kind, self.value))


class BatchAction:
    def __init__(self, kind: str, devices: list[Device] | None = None):
        self.kind = kind
        self.devices = devices or []

    @staticmethod
    def selected(devices: list[Device]) -> BatchAction:
        return BatchAction("selected", devices)

    @staticmethod
    def unresponsive() -> BatchAction:
        return BatchAction("unresponsive")

    @staticmethod
    def disabled_integrations() -> BatchAction:
        return BatchAction("disabledIntegrations")

    @staticmethod
    def all() -> BatchAction:
        return BatchAction("all")
