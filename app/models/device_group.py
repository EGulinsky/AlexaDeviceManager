from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class DeviceGroup:
    id: str
    name: str
    member_endpoint_ids: set[str] = field(default_factory=set)
