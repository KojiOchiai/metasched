from dataclasses import dataclass, field
from typing import Literal

StoreType = Literal["cold_4", "cold_20", "cold_80", "ambient", "warm_30", "warm_37"]


@dataclass
class LiquidName:
    name: str
    store: StoreType
    aliases: list[str] = field(default_factory=list)


@dataclass
class LabwareType:
    name: str
    aliases: list[str] = field(default_factory=list)


class LiquidNameStorage:
    _liquid_names: list[LiquidName] = field(default_factory=list)

    def is_liquid_name(self, name: str) -> bool:
        return any(
            name == liquid_name.name or name in liquid_name.aliases
            for liquid_name in self._liquid_names
        )

    def add_liquid_name(
        self, name: str, store: StoreType, aliases: list[str] | None = None
    ) -> None:
        if aliases is None:
            aliases = []
        if self.is_liquid_name(name):
            raise ValueError(f"Liquid name '{name}' already exists.")
        self._liquid_names.append(LiquidName(name=name, store=store, aliases=aliases))

    def remove_liquid_name(self, name: str) -> None:
        self._liquid_names = [
            liquid_name
            for liquid_name in self._liquid_names
            if liquid_name.name != name
        ]


class LabwareTypeStorage:
    _labware_types: list[LabwareType] = field(default_factory=list)

    def is_labware_type(self, name: str) -> bool:
        return any(
            name == labware_type.name or name in labware_type.aliases
            for labware_type in self._labware_types
        )

    def add_labware_type(self, name: str, aliases: list[str] | None = None) -> None:
        if aliases is None:
            aliases = []
        if self.is_labware_type(name):
            raise ValueError(f"Labware type '{name}' already exists.")
        self._labware_types.append(LabwareType(name=name, aliases=aliases))

    def remove_labware_type(self, name: str) -> None:
        self._labware_types = [
            labware_type
            for labware_type in self._labware_types
            if labware_type.name != name
        ]
