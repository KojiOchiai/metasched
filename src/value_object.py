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
