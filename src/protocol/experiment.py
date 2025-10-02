from datetime import datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID, uuid4

import pint
from pint import UnitRegistry
from pydantic import BaseModel, Field, model_serializer

ureg = UnitRegistry()


# Value objects

StoreType = Literal["cold_4", "cold_20", "cold_80", "ambient", "warm_30", "warm_37"]
RequirementType = Literal["reagent", "new_labware", "existing_labware"]
LiquidUnit = Literal["l", "ml", "ul"]
LiquidName = Annotated[str, Field(min_length=1, max_length=100)]


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


class LabwareType(BaseModel):
    name: str
    max_volume: list[LiquidVolume]
    dead_volume: LiquidVolume = LiquidVolume(volume=0, unit="ml")

    class Config:
        frozen = True


tube50ml = LabwareType(
    name="tube50ml",
    max_volume=[LiquidVolume(volume=50, unit="ml")],
    dead_volume=LiquidVolume(volume=3, unit="ml"),
)
tube1_5ml = LabwareType(
    name="tube1.5ml",
    max_volume=[LiquidVolume(volume=1.5, unit="ml")],
    dead_volume=LiquidVolume(volume=0.2, unit="ml"),
)
plate6well = LabwareType(
    name="plate6well",
    max_volume=[LiquidVolume(volume=10, unit="ml") for _ in range(6)],
)
plate96well = LabwareType(
    name="plate96well",
    max_volume=[LiquidVolume(volume=0.3, unit="ml") for _ in range(96)],
)


class Requirement(BaseModel):
    prepare_to: str


class Reagent(Requirement):
    type: Literal["reagent"] = "reagent"
    labware_type: LabwareType
    reagent_name: str
    volume: LiquidVolume


class BaseLabware(Requirement):
    labware_type: LabwareType


class NewLabware(BaseLabware):
    type: Literal["new_labware"] = "new_labware"


class ExistingLabware(BaseLabware):
    type: Literal["existing_labware"] = "existing_labware"


class Protocol(BaseModel):
    experiment: "Experiment"
    protocol_name: str = Field(min_length=1, max_length=100)
    reagent: dict[str, Reagent] = Field(default_factory=dict)
    new_labware: dict[str, NewLabware] = Field(default_factory=dict)
    existing_labware: dict[str, ExistingLabware] = Field(default_factory=dict)
    duration: timedelta

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
            "experiment_name": self.experiment.name,  # add name instead of object
        }
        return data

    def add_reagent(
        self,
        name: str,
        labware_type: LabwareType,
        reagent_name: str,
        volume: LiquidVolume,
        prepare_to: str,
    ) -> None:
        if name not in self.experiment.reagent_name:
            raise ValueError(f"Reagent name '{name}' not defined in experiment.")
        self.reagent[name] = Reagent(
            labware_type=labware_type,
            reagent_name=reagent_name,
            volume=volume,
            prepare_to=prepare_to,
        )

    def add_new_labware(
        self, name: str, labware_type: LabwareType, prepare_to: str
    ) -> None:
        if name in self.new_labware:
            raise ValueError(f"Labware type '{labware_type}' already exists.")
        self.new_labware[name] = NewLabware(
            labware_type=labware_type, prepare_to=prepare_to
        )

    def add_existing_labware(
        self,
        name: str,
        labware_type: LabwareType,
        prepare_to: str = "",
    ) -> None:
        if name in self.existing_labware:
            raise ValueError(f"Sample name '{name}' already exists.")
        self.existing_labware[name] = ExistingLabware(
            labware_type=labware_type,
            prepare_to=prepare_to,
        )

    def __call__(self, **kwds: "ParentLabware") -> "ProtocolCall":
        for name, labware in kwds.items():
            if name not in self.existing_labware:
                raise ValueError(f"Labware name '{name}' not found in protocol.")
            if self.existing_labware[name].labware_type != labware.labware_type:
                raise ValueError(
                    f"Labware type mismatch for '{name}': "
                    f"expected '{self.existing_labware[name].labware_type}', "
                    f"got '{labware.labware_type}'."
                )
        call = ProtocolCall(
            experiment=self.experiment,
            protocol_name=self.protocol_name,
            reagent=self.reagent,
            new_labware=self.new_labware,
            existing_labware=self.existing_labware,
            duration=self.duration,
            args=kwds,
        )
        self.experiment.scenario.append(call)
        return call


class ParentLabware(BaseModel):
    protocol_id: UUID = Field(default_factory=uuid4)
    labware_label: str = Field(min_length=1, max_length=100)
    labware_type: LabwareType


class ProtocolCall(Protocol):
    id: UUID = Field(default_factory=uuid4)
    args: dict[str, ParentLabware] = Field(default_factory=dict)
    scheduled_time: datetime | None = None
    started_time: datetime | None = None
    finished_time: datetime | None = None

    def __post_init__(self):
        if set(self.args.keys()) != set(self.existing_labware.keys()):
            raise ValueError("Arguments do not match existing labware names.")

    def get(self, name: str) -> ParentLabware:
        if name in self.existing_labware:
            return ParentLabware(
                protocol_id=self.id,
                labware_label=name,
                labware_type=self.existing_labware[name].labware_type,
            )
        if name in self.new_labware:
            return ParentLabware(
                protocol_id=self.id,
                labware_label=name,
                labware_type=self.new_labware[name].labware_type,
            )
        raise ValueError(f"Labware name '{name}' not found in protocol.")


class Store(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    args: dict[str, ParentLabware] = Field(default_factory=dict)
    type: StoreType
    duration: timedelta

    def get(self, name: str) -> ParentLabware:
        if name in self.args:
            return ParentLabware(
                protocol_id=self.id,
                labware_label=name,
                labware_type=self.args[name].labware_type,
            )
        raise ValueError(f"Labware name '{name}' not found in store.")


class Experiment(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    reagent_name: list[str] = Field(default_factory=list)
    protocols: list[Protocol] = Field(default_factory=list)
    scenario: list[ProtocolCall | Store] = Field(default_factory=list)

    def __post__init__(self):
        if len(set(self.reagent_name)) != len(self.reagent_name):
            raise ValueError("Duplicate reagent names found.")

    def new_reagent_name(self, name: str) -> None:
        if name in self.reagent_name:
            raise ValueError(f"Reagent name '{name}' already exists.")
        self.reagent_name.append(name)

    def new_protocol(self, protocol_name: str, duration: timedelta) -> Protocol:
        if any(p.protocol_name == protocol_name for p in self.protocols):
            raise ValueError(f"Protocol name '{protocol_name}' already exists.")
        protocol = Protocol(
            experiment=self,
            protocol_name=protocol_name,
            duration=duration,
        )
        self.protocols.append(protocol)
        return protocol

    def calc_resources(self) -> list[Reagent | NewLabware | ExistingLabware]:
        reagents: list[Reagent] = []
        for protocol in self.protocols:
            reagents.extend(protocol.reagent.values())
        grouped_reagents = self.group_reagents(reagents)
        summed_reagents = self.sum_reagent_volumes(grouped_reagents)

        resources: list[Reagent | NewLabware | ExistingLabware] = []
        for reqs in summed_reagents.values():
            resources.extend(reqs)
        for protocol in self.protocols:
            resources.extend(protocol.new_labware.values())
            resources.extend(protocol.existing_labware.values())
        return resources

    def group_reagents(
        self, reagents: list[Reagent]
    ) -> dict[tuple[str, str], list[Reagent]]:
        groups: dict[tuple[str, str], list[Reagent]] = {}

        for reagent in reagents:
            key = (
                reagent.labware_type.name,
                reagent.reagent_name,
            )
            if key not in groups:
                groups[key] = []
            groups[key].append(reagent)
        return groups

    def sum_reagent_volumes(
        self, reagents: dict[tuple[str, str], list[Reagent]]
    ) -> dict[tuple[str, str], list[Reagent]]:
        summed: dict[tuple[str, str], list[Reagent]] = {}
        for (_, reagent_name), reqs in reagents.items():
            labware_type = reqs[0].labware_type
            if len(labware_type.max_volume) != 1:
                raise NotImplementedError(
                    "Currently only labware types with a single max volume are supported."
                )
            total_volume = sum(req.volume.to_ml() for req in reqs)
            volumes = self.volume_list(
                total_volume,
                max(lv.to_ml() for lv in labware_type.max_volume),
                labware_type.dead_volume.to_ml(),
            )
            summed[(labware_type.name, reagent_name)] = [
                Reagent(
                    labware_type=labware_type,
                    reagent_name=reagent_name,
                    volume=LiquidVolume(volume=vol, unit="ml"),
                    prepare_to="",
                )
                for vol in volumes
            ]
        return summed

    def volume_list(
        self, total_volume: float, max_volume: float, dead_volume: float
    ) -> list[float]:
        volumes = []
        while total_volume > 0:
            if total_volume + dead_volume > max_volume:
                volumes.append(max_volume)
                total_volume -= max_volume - dead_volume
            else:
                volumes.append(total_volume + dead_volume)
                total_volume = 0
        return volumes


if __name__ == "__main__":
    exp = Experiment(name="Test Experiment")
    exp.new_reagent_name("medium")
    exp.new_reagent_name("trypsin")
    exp.new_reagent_name("DMEM")
    exp.new_reagent_name("PBS")

    medium_change = exp.new_protocol("medium_change", duration=timedelta(minutes=30))
    medium_change.add_reagent(
        name="medium",
        labware_type=tube50ml,
        reagent_name="medium",
        volume=LiquidVolume(volume=20, unit="ml"),
        prepare_to="tube_rack1/1",
    )
    medium_change.add_existing_labware(
        name="sample1", labware_type=plate6well, prepare_to="LS/1"
    )

    passage = exp.new_protocol("passage", duration=timedelta(hours=1))
    passage.add_reagent(
        name="medium",
        labware_type=tube50ml,
        reagent_name="medium",
        volume=LiquidVolume(volume=20, unit="ml"),
        prepare_to="tube_rack1/1",
    )
    passage.add_reagent(
        name="trypsin",
        labware_type=tube50ml,
        reagent_name="trypsin",
        volume=LiquidVolume(volume=5, unit="ml"),
        prepare_to="tube_rack1/2",
    )
    passage.add_reagent(
        name="PBS",
        labware_type=tube50ml,
        reagent_name="PBS",
        volume=LiquidVolume(volume=20, unit="ml"),
        prepare_to="tube_rack1/3",
    )
    passage.add_reagent(
        name="DMEM",
        labware_type=tube50ml,
        reagent_name="DMEM",
        volume=LiquidVolume(volume=20, unit="ml"),
        prepare_to="tube_rack1/4",
    )
    passage.add_existing_labware(
        name="cell_plate", labware_type=plate6well, prepare_to="LS/1"
    )
    passage.add_new_labware(
        name="new_cell_plate", labware_type=plate6well, prepare_to="LS/2"
    )
    print(exp.model_dump_json(indent=2))
    resources = exp.calc_resources()
    for res in resources:
        print(res.model_dump_json(indent=2))
