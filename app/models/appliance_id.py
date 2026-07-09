from __future__ import annotations
import re
import base64
import json
from dataclasses import dataclass


@dataclass
class DecodedApplianceID:
    skill_id: str
    stage: str | None
    domain: str
    object_id: str


class ApplianceIDParser:
    _regex = re.compile(r"^SKILL_([A-Za-z0-9+/=]+)_(.+)$")

    @staticmethod
    def decode(appliance_id: str) -> DecodedApplianceID | None:
        match = ApplianceIDParser._regex.match(appliance_id)
        if not match:
            return None

        base64_part = match.group(1)
        suffix = match.group(2)

        try:
            json_data = base64.b64decode(base64_part)
            payload: dict[str, str] = json.loads(json_data)
            skill_id = payload.get("skillId")
            if not skill_id:
                return None
        except (json.JSONDecodeError, base64.binascii.Error, UnicodeDecodeError):
            return None

        domain_split = suffix.split("#", maxsplit=1)
        domain = domain_split[0] if domain_split else suffix
        object_id = domain_split[1] if len(domain_split) > 1 else ""

        return DecodedApplianceID(
            skill_id=skill_id,
            stage=payload.get("stage"),
            domain=domain,
            object_id=object_id,
        )
