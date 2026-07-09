from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class AlexaRegion:
    id: str
    label: str
    retail_domain: str

    @property
    def base_url(self) -> str:
        return f"https://{self.id}"

    @property
    def sign_in_url(self) -> str:
        return f"https://www.{self.retail_domain}/"


AlexaRegion.candidates = [
    AlexaRegion(id="alexa.amazon.de", label="Germany (alexa.amazon.de)", retail_domain="amazon.de"),
    AlexaRegion(id="alexa.amazon.com", label="USA (alexa.amazon.com)", retail_domain="amazon.com"),
    AlexaRegion(id="pitangui.amazon.com", label="USA – Pitangui (pitangui.amazon.com)", retail_domain="amazon.com"),
    AlexaRegion(id="layla.amazon.com", label="EU/UK (layla.amazon.com)", retail_domain="amazon.co.uk"),
    AlexaRegion(id="alexa.amazon.co.jp", label="Japan (alexa.amazon.co.jp)", retail_domain="amazon.co.jp"),
]
