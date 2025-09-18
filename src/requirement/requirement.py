from datetime import timedelta
from typing import Annotated, Literal
from uuid import UUID, uuid4

import pint
from pint import UnitRegistry
from pydantic import (
    BaseModel,
    Field,
    PositiveFloat,
    field_serializer,
    field_validator,
    model_validator,
)

from src.requirement.label import StoreType

ureg = UnitRegistry()


# Value objects

LiquidUnit = Literal["l", "ml", "ul"]
RequirementType = Literal["reagent", "new_labware", "existing_labware"]
LiquidName = Annotated[str, Field(min_length=1, max_length=100)]
LabwareType = Annotated[str, Field(min_length=1, max_length=100)]


class LiquidVolume(BaseModel):
    volume: PositiveFloat
    unit: LiquidUnit

    class Config:
        frozen = True

    def __str__(self) -> str:
        return f"{self.volume}{self.unit}"

    def to_pint(self) -> pint.Quantity:
        return ureg.Quantity(self.volume, self.unit)


class Liquid(BaseModel):
    name: LiquidName
    volume: LiquidVolume

    class Config:
        frozen = True

    @staticmethod
    def from_primitive(name: str, volume: float, unit: LiquidUnit) -> "Liquid":
        return Liquid(name=name, volume=LiquidVolume(volume=volume, unit=unit))

    def __str__(self) -> str:
        return f"Liquid({self.name}, {self.volume})"

    def take_volume(self, volume: float, unit: LiquidUnit) -> tuple["Liquid", "Liquid"]:
        """Takes a specified volume from the current liquid.

        Args:
            volume (float): The volume of liquid to take
            unit (LiquidUnit): The unit of measurement ("l", "ml", "ul")

        Returns:
            tuple[Liquid, Liquid]: A tuple containing (remaining liquid, taken liquid)

        Raises:
            ValueError: If the requested volume exceeds the available volume
        """
        liquid_volume = LiquidVolume(volume=volume, unit=unit)

        use_volume = liquid_volume.to_pint()
        self_volume = self.volume.to_pint()
        if use_volume > self_volume:
            raise ValueError("Requested volume exceeds available volume")

        remaining_volume: pint.Quantity = self_volume - use_volume
        return (
            Liquid(
                name=self.name,
                volume=LiquidVolume(
                    volume=remaining_volume.magnitude, unit=self.volume.unit
                ),
            ),
            Liquid(
                name=self.name,
                volume=LiquidVolume(
                    volume=use_volume.magnitude, unit=liquid_volume.unit
                ),
            ),
        )


class Requirement(BaseModel):
    type: RequirementType
    prepare_to: str

    class Config:
        frozen = True


class Reagent(Requirement):
    type: RequirementType = "reagent"
    name: LiquidName
    volume: LiquidVolume
    container_type: LabwareType
    replenished_within: timedelta | None = Field(default=None)

    class Config:
        frozen = True


class BaseLabware(Requirement):
    id: UUID = Field(default_factory=uuid4)
    labware_type: LabwareType
    discard: bool = Field(default=False)
    store: set[StoreType] | None = Field(default=None)

    @model_validator(mode="after")
    def check_mutual_exclusion(self):
        if self.discard and (self.store is not None):
            raise ValueError("discard and store can not be used together")
        if not self.discard and (self.store is None):
            raise ValueError("discard or store must be used")
        return self

    @field_serializer("store")
    def serialize_store(self, value):
        if isinstance(value, set):
            return list(value)
        return value

    @field_validator("store")
    def validate_store(cls, value):
        if isinstance(value, list):
            return set(value)
        return value


class NewLabware(BaseLabware):
    type: RequirementType = "new_labware"

    class Config:
        frozen = True


class ExistingLabware(BaseLabware):
    type: RequirementType = "existing_labware"
    identical_to: UUID | None = (
        None
        # UUID of another New/ExistingLabware requirement.
        # None means this labware need to imported from elsewhere.
    )

    class Config:
        frozen = True
