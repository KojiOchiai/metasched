from datetime import datetime, timedelta
from enum import Enum

from pydantic import BaseModel

from protocol.requirement import (
    BaseLabware,
    ExistingLabware,
    Field,
    NewLabware,
    Reagent,
)
from src.protocol.label import StoreType


class NodeType(Enum):
    PROTOCOL = "protocol"
    STORE = "store"
    DISCARD = "discard"
    LOADING = "loading"
    UNLOADING = "unloading"


class RequirementSetup(BaseModel):
    requirement: Reagent | NewLabware
    prepare_to: str


class ExistingLabwareSetup(BaseModel):
    requirement: ExistingLabware
    prepare_to: str


class Node(BaseModel):
    node_type: NodeType
    existing_labwares: dict[str, ExistingLabwareSetup] = Field(default_factory=dict)
    scheduled_time: datetime | None = None
    started_time: datetime | None = None
    finished_time: datetime | None = None

    def __post_init__(self):
        if len(set(self.existing_labwares.keys())) != len(self.existing_labwares):
            raise ValueError("Duplicate existing labware names found.")

    def __call__(self, **kwds: BaseLabware) -> dict[str, BaseLabware]:
        for name, labware in kwds.items():
            if name not in self.existing_labwares:
                raise ValueError(
                    f"Labware name '{name}' not found in existing labwares."
                )
            if (
                self.existing_labwares[name].requirement.labware_type
                != labware.labware_type
            ):
                raise ValueError(
                    f"Labware type mismatch for '{name}': "
                    f"expected '{self.existing_labwares[name].requirement.labware_type}', "
                    f"got '{labware.labware_type}'."
                )
            self.existing_labwares[name].requirement.parent_labware = labware
        return self.returns()

    def returns(self) -> dict[str, BaseLabware]:
        return {
            name: labware.requirement
            for name, labware in self.existing_labwares.items()
        }


class Protocol(Node):
    node_type: NodeType = NodeType.PROTOCOL
    requirements: dict[str, RequirementSetup] = Field(default_factory=dict)
    protocol_name: str
    duration: timedelta

    def __post_init__(self):
        all_names = set(self.existing_labwares.keys()).union(
            set(self.requirements.keys())
        )
        if len(all_names) != len(self.existing_labwares) + len(self.requirements):
            raise ValueError(
                "Duplicate names found between existing labwares and requirements."
            )

    def returns(self) -> dict[str, BaseLabware]:
        all_labwares = super().returns()
        req_labwares = {
            name: req.requirement
            for name, req in self.requirements.items()
            if isinstance(req.requirement, BaseLabware)
        }
        all_labwares.update(req_labwares)
        return all_labwares


class Store(Node):
    node_type: NodeType = NodeType.STORE
    store_condition: StoreType
    optimal_time: timedelta | None = None


class Loading(Node):
    node_type: NodeType = NodeType.LOADING
    labware: NewLabware
    store_condition: StoreType

    def __post_init__(self):
        if len(self.existing_labwares) != 0:
            raise ValueError("Loading node cannot have existing labwares.")

    def returns(self) -> dict[str, NewLabware]:
        return {"new_labware": self.labware}


class Unloading(Node):
    node_type: NodeType = NodeType.UNLOADING

    def __post_init__(self):
        if len(self.existing_labwares) != 1:
            raise ValueError("Unloading node must have exactly one existing labware.")

    def returns(self) -> dict[str, BaseLabware]:
        return {}
