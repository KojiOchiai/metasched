import re
from typing import Literal

import pint
from pint import UnitRegistry
from pydantic import BaseModel, Field

ureg = UnitRegistry()


# Value objects

StoreType = Literal["cold_4", "cold_20", "cold_80", "ambient", "warm_30", "warm_37"]
LiquidUnit = Literal["l", "ml", "ul"]


class LiquidVolume(BaseModel):
    volume: float = Field(ge=0)
    unit: LiquidUnit

    class Config:
        frozen = True

    def __str__(self) -> str:
        return f"{self.volume}{self.unit}"

    def to_pint(self) -> pint.Quantity:
        return ureg.Quantity(self.volume, self.unit)

    def to_ml(self) -> float:
        return self.to_pint().to(ureg.ml).magnitude

    @classmethod
    def from_string(cls, s: str) -> "LiquidVolume":
        # e.g. "20ml", "1.5l", "300ul"
        s = s.strip().lower()
        match = re.match(r"^([\d.]+)\s*(l|ml|ul)$", s)
        if not match:
            raise ValueError(f"Invalid liquid volume string '{s}'")
        volume, unit = match.groups()
        return cls(volume=float(volume), unit=unit)  # type: ignore
