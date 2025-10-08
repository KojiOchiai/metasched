from datetime import timedelta

from pydantic import BaseModel, Field, model_serializer

from src.labware import LabwareType
from src.value_object import LiquidVolume


class Requirement(BaseModel):
    prepare_to: str


class Reagent(Requirement):
    labware_type: str
    reagent_name: str
    volume: LiquidVolume


class BaseLabware(Requirement):
    labware_type: str


class NewLabware(BaseLabware):
    pass


class ExistingLabware(BaseLabware):
    pass


class Protocol(BaseModel):
    protocol_name: str = Field(min_length=1, max_length=100)
    reagent: dict[str, Reagent]
    new_labware: dict[str, NewLabware]
    existing_labware: dict[str, ExistingLabware]
    duration: timedelta

    class Config:
        frozen = True

    @model_serializer
    def serialize_model(self) -> dict:
        data = {
            "protocol_name": self.protocol_name,
            "reagent": {k: v.model_dump() for k, v in self.reagent.items()},
            "new_labware": {k: v.model_dump() for k, v in self.new_labware.items()},
            "existing_labware": {
                k: v.model_dump() for k, v in self.existing_labware.items()
            },
            "duration": str(self.duration),
        }
        return data

    def validate_requirements(
        self, labware_types: dict[str, LabwareType], reagent_names: list[str]
    ) -> None:
        for r in self.reagent.values():
            if r.labware_type not in labware_types:
                raise ValueError(f"Labware type '{r.labware_type}' not found.")
            if r.reagent_name not in reagent_names:
                raise ValueError(f"Reagent name '{r.reagent_name}' not found.")
        for nl in self.new_labware.values():
            if nl.labware_type not in labware_types:
                raise ValueError(f"Labware type '{nl.labware_type}' not found.")
        for el in self.existing_labware.values():
            if el.labware_type not in labware_types:
                raise ValueError(f"Labware type '{el.labware_type}' not found.")

    @classmethod
    def builder(cls, protocol_name: str, duration: timedelta) -> "ProtocolBuilder":
        """Create a new ProtocolBuilder instance"""
        return ProtocolBuilder(protocol_name, duration)


class ProtocolBuilder:
    """Builder class for creating Protocol objects"""

    protocol_name: str
    duration: timedelta
    _reagent: dict[str, Reagent]
    _new_labware: dict[str, NewLabware]
    _existing_labware: dict[str, ExistingLabware]

    def __init__(self, protocol_name: str, duration: timedelta):
        self.protocol_name = protocol_name
        self.duration = duration
        self._reagent = {}
        self._new_labware = {}
        self._existing_labware = {}

    def reagent(
        self,
        labware_type: str,
        reagent_name: str,
        volume: str,
        name: str | None = None,
        prepare_to: str = "",
    ) -> "ProtocolBuilder":
        name = name or reagent_name
        if name in self._reagent:
            raise ValueError(f"Duplicate reagent name '{name}' found.")
        self._reagent[name] = Reagent(
            labware_type=labware_type,
            reagent_name=reagent_name,
            volume=LiquidVolume.from_string(volume),
            prepare_to=prepare_to,
        )
        return self

    def new_labware(
        self, name: str, labware_type: str, prepare_to: str = ""
    ) -> "ProtocolBuilder":
        """Add a new labware requirement to the protocol"""
        if name in self._new_labware:
            raise ValueError(f"Duplicate new labware name '{name}' found.")
        self._new_labware[name] = NewLabware(
            labware_type=labware_type,
            prepare_to=prepare_to,
        )
        return self

    def existing_labware(
        self, name: str, labware_type: str, prepare_to: str = ""
    ) -> "ProtocolBuilder":
        """Add an existing labware requirement to the protocol"""
        if name in self._existing_labware:
            raise ValueError(f"Duplicate existing labware name '{name}' found.")
        self._existing_labware[name] = ExistingLabware(
            labware_type=labware_type,
            prepare_to=prepare_to,
        )
        return self

    def build(self) -> Protocol:
        """Build and return the final Protocol object"""
        return Protocol(
            protocol_name=self.protocol_name,
            reagent=self._reagent,
            new_labware=self._new_labware,
            existing_labware=self._existing_labware,
            duration=self.duration,
        )


class Experiment(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    reagent_names: list[str] = Field(default_factory=list)
    labware_types: list[LabwareType] = Field(default_factory=list)
    protocols: list[Protocol] = Field(default_factory=list)

    class Config:
        frozen = True

    def __post__init__(self):
        if len(set(self.reagent_names)) != len(self.reagent_names):
            raise ValueError("Duplicate reagent names found.")

    @classmethod
    def builder(cls, name: str) -> "ExperimentBuilder":
        """Create a new ExperimentBuilder instance"""
        return ExperimentBuilder(name)


class ExperimentBuilder:
    """Builder class for creating Experiment objects with a fluent interface"""

    name: str
    _reagent_names: list[str]
    _labware_types: list[LabwareType]
    _protocols: list[Protocol]

    def __init__(self, name: str):
        self.name = name
        self._reagent_names = []
        self._labware_types = []
        self._protocols = []

    def reagent_names(self, *name: str) -> "ExperimentBuilder":
        """Add reagent names to the experiment"""
        for n in name:
            if n in self._reagent_names:
                raise ValueError(f"Duplicate reagent name '{n}' found.")
            self._reagent_names.append(n)
        return self

    def labware_types(self, *labware_types: LabwareType) -> "ExperimentBuilder":
        """Add labware types to the experiment"""
        for lt in labware_types:
            if lt in self._labware_types:
                raise ValueError(f"Duplicate labware type '{lt.name}' found.")
            self._labware_types.append(lt)
        return self

    def protocols(self, *protocols: Protocol) -> "ExperimentBuilder":
        """Add a protocol to the experiment"""
        for p in protocols:
            if p in self._protocols:
                raise ValueError(f"Duplicate protocol '{p.protocol_name}' found.")
            self._protocols.append(p)
        return self

    def build(self) -> Experiment:
        """Build and return the final Experiment object"""
        # check reagent names in protocols
        for protocol in self._protocols:
            protocol.validate_requirements(
                {lt.name: lt for lt in self._labware_types}, self._reagent_names
            )
        return Experiment(
            name=self.name,
            reagent_names=self._reagent_names,
            labware_types=self._labware_types,
            protocols=self._protocols,
        )


if __name__ == "__main__":
    from src.labware import labware_types

    # ========== Original approach (existing code) ==========
    print("=== Original Builder Pattern ===")

    # define protocols using builder pattern
    medium_change = (
        Protocol.builder("medium_change", timedelta(minutes=30))
        .reagent("tube50ml", "medium", volume="20ml", prepare_to="tube_rack1/1")
        .existing_labware("cell_plate", "plate6well", prepare_to="LS/1")
        .build()
    )

    passage = (
        Protocol.builder("passage", timedelta(minutes=45))
        .reagent("tube50ml", "medium", volume="20ml", prepare_to="tube_rack1/1")
        .reagent("tube50ml", "trypsin", volume="5ml", prepare_to="tube_rack1/2")
        .reagent("tube50ml", "PBS", volume="20ml", prepare_to="tube_rack1/3")
        .reagent("tube50ml", "DMEM", volume="20ml", prepare_to="tube_rack1/4")
        .existing_labware("cell_plate", "plate6well", prepare_to="LS/1")
        .new_labware("new_cell_plate", "plate6well", prepare_to="LS/2")
        .build()
    )

    # define experiment using builder pattern
    experiment = (
        Experiment.builder("HEK293A culture")
        .reagent_names("medium", "trypsin", "DMEM", "PBS")
        .labware_types(*labware_types)
        .protocols(medium_change, passage)
        .build()
    )

    print(experiment.model_dump_json(indent=2))
