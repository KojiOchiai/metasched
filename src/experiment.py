from datetime import datetime, timedelta
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_serializer

from src.labware import LabwareType
from src.value_object import LiquidVolume, StoreType


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
        labware_type: str,
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

    def add_new_labware(self, name: str, labware_type: str, prepare_to: str) -> None:
        if name in self.new_labware:
            raise ValueError(f"Labware type '{labware_type}' already exists.")
        self.new_labware[name] = NewLabware(
            labware_type=labware_type, prepare_to=prepare_to
        )

    def add_existing_labware(
        self,
        name: str,
        labware_type: str,
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
            protocol=self,
            duration=self.duration,
            args=kwds,
        )
        self.experiment.protocol_calls.append(call)
        return call


class ParentLabware(BaseModel):
    node_id: UUID = Field(default_factory=uuid4)
    labware_label: str = Field(min_length=1, max_length=100)
    labware_type: str


class ScenarioNode(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    duration: timedelta


class ProtocolCall(ScenarioNode):
    protocol: Protocol
    args: dict[str, ParentLabware] = Field(default_factory=dict)
    scheduled_time: datetime | None = None
    started_time: datetime | None = None
    finished_time: datetime | None = None

    def get(self, name: str) -> ParentLabware:
        if name in self.protocol.existing_labware:
            return ParentLabware(
                node_id=self.id,
                labware_label=name,
                labware_type=self.protocol.existing_labware[name].labware_type,
            )
        if name in self.protocol.new_labware:
            return ParentLabware(
                node_id=self.id,
                labware_label=name,
                labware_type=self.protocol.new_labware[name].labware_type,
            )
        raise ValueError(f"Labware name '{name}' not found in protocol.")


class Store(ScenarioNode):
    type: StoreType
    labware: ParentLabware

    def get(self) -> ParentLabware:
        return ParentLabware(
            node_id=self.id,
            labware_label=self.labware.labware_label,
            labware_type=self.labware.labware_type,
        )


class MoveIn(ScenarioNode):
    labware_type: str

    def get(self) -> ParentLabware:
        return ParentLabware(
            node_id=self.id,
            labware_label=f"move_in_{self.labware_type}",
            labware_type=self.labware_type,
        )


class MoveOut(ScenarioNode):
    labware: ParentLabware

    def get(self) -> None:
        return None


class Experiment(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    reagent_name: list[str] = Field(default_factory=list)
    protocols: list[Protocol] = Field(default_factory=list)
    protocol_calls: list[ProtocolCall] = Field(default_factory=list)
    stores: list[Store] = Field(default_factory=list)
    moves_in: list[MoveIn] = Field(default_factory=list)
    moves_out: list[MoveOut] = Field(default_factory=list)

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

    def get_scenario_nodes(self) -> list[ProtocolCall | Store | MoveIn | MoveOut]:
        return self.protocol_calls + self.stores + self.moves_in + self.moves_out

    def check_parent_labware(self, labware: ParentLabware) -> None:
        nodes = {p.id: p for p in self.get_scenario_nodes()}
        if labware.node_id not in nodes:
            raise ValueError(f"Node ID '{labware.node_id}' not found.")
        node = nodes[labware.node_id]
        if isinstance(node, ProtocolCall):
            labware_def = node.get(labware.labware_label)
            if labware_def is None:
                raise ValueError(
                    f"Labware name '{labware.labware_label}' not found in protocol call."
                )
            if labware_def.labware_type != labware.labware_type:
                raise ValueError(
                    f"Labware type mismatch for '{labware.labware_label}': "
                    f"expected '{labware_def.labware_type}', got '{labware.labware_type}'."
                )
        if isinstance(node, Store) or isinstance(node, MoveOut):
            if node.labware.labware_label != labware.labware_label:
                raise ValueError(
                    f"Labware label mismatch: expected '{node.labware.labware_label}', "
                    f"got '{labware.labware_label}'."
                )
            if node.labware.labware_type != labware.labware_type:
                raise ValueError(
                    f"Labware type mismatch for '{labware.labware_label}': "
                    f"expected '{node.labware.labware_type}', got '{labware.labware_type}'."
                )

    def store(self, type: StoreType, duration: timedelta, labware: ParentLabware):
        self.check_parent_labware(labware)
        store = Store(type=type, duration=duration, labware=labware)
        self.stores.append(store)
        return store.get()

    def move_in(self, labware_type: str, duration: timedelta = timedelta(minutes=3)):
        move_in = MoveIn(labware_type=labware_type, duration=duration)
        self.moves_in.append(move_in)
        return move_in.get()

    def move_out(
        self,
        labware: ParentLabware,
        duration: timedelta = timedelta(minutes=3),
    ):
        self.check_parent_labware(labware)
        move_out = MoveOut(duration=duration, labware=labware)
        self.moves_out.append(move_out)
        return move_out.get()

    def calc_resources(
        self, labware_types: dict[str, LabwareType]
    ) -> list[Reagent | NewLabware | ExistingLabware]:
        reagents: list[Reagent] = []
        for protocol_call in self.get_scenario_nodes():
            if not isinstance(protocol_call, ProtocolCall):
                continue
            reagents.extend(protocol_call.protocol.reagent.values())
        grouped_reagents = self.group_reagents(reagents)
        summed_reagents = self.sum_reagent_volumes(grouped_reagents, labware_types)

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
                reagent.labware_type,
                reagent.reagent_name,
            )
            if key not in groups:
                groups[key] = []
            groups[key].append(reagent)
        return groups

    def sum_reagent_volumes(
        self,
        reagents: dict[tuple[str, str], list[Reagent]],
        labware_types: dict[str, LabwareType],
    ) -> dict[tuple[str, str], list[Reagent]]:
        summed: dict[tuple[str, str], list[Reagent]] = {}
        for (_, reagent_name), reqs in reagents.items():
            if reqs[0].labware_type not in labware_types:
                raise ValueError(
                    f"Labware type '{reqs[0].labware_type}' not found in labware types."
                )
            labware_type = labware_types[reqs[0].labware_type]
            if len(labware_type.max_volume) != 1:
                raise NotImplementedError(
                    "Currently only labware types with a single max volume are supported."
                )
            volume_list = [req.volume.to_ml() for req in reqs]
            volumes = self.compress_list(
                volume_list,
                max(lv.to_ml() for lv in labware_type.max_volume),
                labware_type.dead_volume.to_ml(),
            )
            summed[(labware_type.name, reagent_name)] = [
                Reagent(
                    labware_type=labware_type.name,
                    reagent_name=reagent_name,
                    volume=LiquidVolume(volume=vol, unit="ml"),
                    prepare_to="",
                )
                for vol in volumes
            ]
        return summed

    def compress_list(
        self, volume_list: list[float], max_volume: float, dead_volume: float
    ) -> list[float]:
        result: list[float] = []
        current_sum = 0.0
        for x in volume_list:
            # if adding x does not exceed max_volume, add it to current_sum
            if current_sum + x + dead_volume <= max_volume:
                current_sum += x
            else:
                # if current_sum > 0: make new group
                if current_sum > 0:
                    result.append(current_sum + dead_volume)
                current_sum = x
        # add the last remaining
        if current_sum > 0:
            result.append(current_sum + dead_volume)
        return result


if __name__ == "__main__":
    # define experiment
    exp = Experiment(name="Test Experiment")

    # define reagent names
    exp.new_reagent_name("medium")
    exp.new_reagent_name("trypsin")
    exp.new_reagent_name("DMEM")
    exp.new_reagent_name("PBS")

    # define protocols
    medium_change = exp.new_protocol("medium_change", duration=timedelta(minutes=30))
    medium_change.add_reagent(
        name="medium",
        labware_type="tube50ml",
        reagent_name="medium",
        volume=LiquidVolume(volume=20, unit="ml"),
        prepare_to="tube_rack1/1",
    )
    medium_change.add_existing_labware(
        name="cell_plate", labware_type="plate6well", prepare_to="LS/1"
    )

    passage = exp.new_protocol("passage", duration=timedelta(hours=1))
    passage.add_reagent(
        name="medium",
        labware_type="tube50ml",
        reagent_name="medium",
        volume=LiquidVolume(volume=20, unit="ml"),
        prepare_to="tube_rack1/1",
    )
    passage.add_reagent(
        name="trypsin",
        labware_type="tube50ml",
        reagent_name="trypsin",
        volume=LiquidVolume(volume=5, unit="ml"),
        prepare_to="tube_rack1/2",
    )
    passage.add_reagent(
        name="PBS",
        labware_type="tube50ml",
        reagent_name="PBS",
        volume=LiquidVolume(volume=20, unit="ml"),
        prepare_to="tube_rack1/3",
    )
    passage.add_reagent(
        name="DMEM",
        labware_type="tube50ml",
        reagent_name="DMEM",
        volume=LiquidVolume(volume=20, unit="ml"),
        prepare_to="tube_rack1/4",
    )
    passage.add_existing_labware(
        name="cell_plate", labware_type="plate6well", prepare_to="LS/1"
    )
    passage.add_new_labware(
        name="new_cell_plate", labware_type="plate6well", prepare_to="LS/2"
    )

    # define scenario
    cell_plate = exp.move_in(labware_type="plate6well")
    mc1 = medium_change(cell_plate=cell_plate)
    exp.store(
        type="warm_30", duration=timedelta(hours=24), labware=mc1.get("cell_plate")
    )
    passage1 = passage(cell_plate=cell_plate)

    print(exp.model_dump_json(indent=2))

    print("")
    from src.labware import labware_types

    reagents = exp.calc_resources({lt.name: lt for lt in labware_types})
    for r in reagents:
        print(r.model_dump_json(indent=2))
