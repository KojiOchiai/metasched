from pydantic import BaseModel

from src.value_object import LiquidVolume


class LabwareType(BaseModel):
    name: str
    max_volume: list[LiquidVolume]
    dead_volume: LiquidVolume = LiquidVolume(volume=0, unit="ml")

    class Config:
        frozen = True


labware_types: list[LabwareType] = [
    LabwareType(
        name="tube50ml",
        max_volume=[LiquidVolume(volume=50, unit="ml")],
        dead_volume=LiquidVolume(volume=3, unit="ml"),
    ),
    LabwareType(
        name="tube1.5ml",
        max_volume=[LiquidVolume(volume=1.5, unit="ml")],
        dead_volume=LiquidVolume(volume=0.2, unit="ml"),
    ),
    LabwareType(
        name="plate6well",
        max_volume=[LiquidVolume(volume=10, unit="ml") for _ in range(6)],
    ),
    LabwareType(
        name="plate96well",
        max_volume=[LiquidVolume(volume=0.3, unit="ml") for _ in range(96)],
    ),
]
