from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from .appliance_id import ApplianceIDParser, DecodedApplianceID


class Connectivity(Enum):
    OK = "ok"
    UNREACHABLE = "unreachable"
    UNKNOWN = "unknown"


@dataclass
class Device:
    appliance_id: str
    friendly_name: str
    decoded: DecodedApplianceID | None
    connectivity: Connectivity = Connectivity.UNKNOWN
    manufacturer_name: str | None = None
    display_category: str | None = None
    endpoint_id: str | None = None
    associated_unit_id: str | None = None
    raw_fields: dict[str, str] = field(default_factory=dict)

    unknown_skill_id = "unknown"

    @property
    def id(self) -> str:
        return self.appliance_id

    @property
    def skill_id(self) -> str | None:
        return self.decoded.skill_id if self.decoded else None

    @property
    def integration_group_key(self) -> str:
        if self.skill_id:
            return self.skill_id
        if self.manufacturer_name == "Amazon":
            return "Amazon"
        return Device.unknown_skill_id

    @property
    def type_label(self) -> str:
        from .lookup_tables import alexa_display_category_label, home_assistant_domain_label
        if self.display_category:
            return alexa_display_category_label(self.display_category)
        kind = self._home_assistant_domain_kind
        if kind:
            return home_assistant_domain_label(kind)
        return "Unknown"

    @property
    def type_symbol_name(self) -> str:
        from .lookup_tables import alexa_display_category_symbol, home_assistant_domain_symbol
        if self.display_category:
            return alexa_display_category_symbol(self.display_category)
        kind = self._home_assistant_domain_kind
        if kind:
            return home_assistant_domain_symbol(kind)
        return "questionmark-circle"

    @property
    def _home_assistant_domain_kind(self) -> str | None:
        if not self.decoded or not self.decoded.domain:
            return None
        return self.decoded.domain.split(":", maxsplit=1)[0] or self.decoded.domain
