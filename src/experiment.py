from datetime import timedelta
from typing import Any, get_args
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_serializer

from src.labware import LabwareType
from src.value_object import LiquidVolume, StoreType


class Requirement(BaseModel):
    labware_type: str
    prepare_to: str


class Labware(Requirement):
    pass


class Reagent(Requirement):
    reagent_name: str
    volume: LiquidVolume


class Protocol(BaseModel):
    protocol_name: str = Field(min_length=1, max_length=100)
    args: dict[str, type | list[str]] = Field(default_factory=dict)
    reagent: list[Reagent]
    new_labware: dict[str, Labware]
    existing_labware: dict[str, Labware]
    duration: timedelta

    class Config:
        frozen = True

    @model_serializer
    def serialize_model(self) -> dict:
        data = {
            "protocol_name": self.protocol_name,
            "reagent": [r.model_dump() for r in self.reagent],
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
        for r in self.reagent:
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
    def builder(
        cls,
        protocol_name: str,
        duration: timedelta,
        args: dict[str, type | list[str]] = {},
    ) -> "ProtocolBuilder":
        """Create a new ProtocolBuilder instance"""
        return ProtocolBuilder(protocol_name, duration, args)

    def get_input_ports(self) -> list[str]:
        return list(self.existing_labware.keys())

    def get_output_ports(self) -> list[str]:
        return list(self.new_labware.keys()) + list(self.existing_labware.keys())


class ProtocolBuilder:
    """Builder class for creating Protocol objects"""

    protocol_name: str
    duration: timedelta
    args: dict[str, type | list[str]]
    _reagent: list[Reagent]
    _new_labware: dict[str, Labware]
    _existing_labware: dict[str, Labware]

    def __init__(
        self,
        protocol_name: str,
        duration: timedelta,
        args: dict[str, type | list[str]] = {},
    ):
        self.protocol_name = protocol_name
        self.duration = duration
        self.args = args
        self._reagent = []
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
        self._reagent.append(
            Reagent(
                labware_type=labware_type,
                reagent_name=reagent_name,
                volume=LiquidVolume.from_string(volume),
                prepare_to=prepare_to,
            )
        )
        return self

    def new_labware(
        self, name: str, labware_type: str, prepare_to: str = ""
    ) -> "ProtocolBuilder":
        """Add a new labware requirement to the protocol"""
        if name in self._new_labware:
            raise ValueError(f"Duplicate new labware name '{name}' found.")
        self._new_labware[name] = Labware(
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
        self._existing_labware[name] = Labware(
            labware_type=labware_type,
            prepare_to=prepare_to,
        )
        return self

    def build(self) -> Protocol:
        """Build and return the final Protocol object"""
        return Protocol(
            protocol_name=self.protocol_name,
            args=self.args,
            reagent=self._reagent,
            new_labware=self._new_labware,
            existing_labware=self._existing_labware,
            duration=self.duration,
        )


class Node(BaseModel):
    protocol_name: str
    args: dict[str, Any] = Field(default_factory=dict)
    id: UUID = Field(default_factory=uuid4)

    class Config:
        frozen = True


class Edge(BaseModel):
    from_node: UUID
    from_port: str
    to_node: UUID
    to_port: str

    class Config:
        frozen = True


class Experiment(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    reagent_names: list[str] = Field(default_factory=list)
    labware_types: list[LabwareType] = Field(default_factory=list)
    protocols: list[Protocol] = Field(default_factory=list)
    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)

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
    _nodes: list[Node]
    _edges: list[Edge]

    def __init__(self, name: str):
        self.name = name
        self._reagent_names = []
        self._labware_types = []
        self._protocols = []
        self._nodes = []
        self._edges = []

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

    def get_protocol(self, protocol_name: str) -> Protocol:
        protocol = next(
            (p for p in self._protocols if p.protocol_name == protocol_name), None
        )
        if protocol is None:
            raise ValueError(f"Protocol '{protocol_name}' not found in experiment.")
        return protocol

    def move_in_protocol(self, labware_type: str) -> Protocol:
        if labware_type not in [lt.name for lt in self._labware_types]:
            raise ValueError(f"Labware type '{labware_type}' not found.")
        number = len(self._protocols) + 1
        move_in = (
            Protocol.builder(f"move_in_{number}", timedelta(minutes=5))
            .new_labware("labware", labware_type, prepare_to="")
            .build()
        )
        self._protocols.append(move_in)
        return move_in

    def move_out_protocol(self, labware_type: str) -> Protocol:
        if labware_type not in [lt.name for lt in self._labware_types]:
            raise ValueError(f"Labware type '{labware_type}' not found.")
        number = len(self._protocols) + 1
        move_out = (
            Protocol.builder(f"move_out_{number}", timedelta(minutes=5))
            .existing_labware("labware", labware_type, prepare_to="")
            .build()
        )
        self._protocols.append(move_out)
        return move_out

    def store_protocol(
        self, labware_type: str, duration: timedelta = timedelta(minutes=5)
    ) -> Protocol:
        if labware_type not in [lt.name for lt in self._labware_types]:
            raise ValueError(f"Labware type '{labware_type}' not found.")
        number = len(self._protocols) + 1
        store = (
            Protocol.builder(
                f"store_{number}",
                duration,
                args={"store_type": list(get_args(StoreType))},
            )
            .existing_labware("labware", labware_type, prepare_to="")
            .build()
        )
        self._protocols.append(store)
        return store

    def move_in(self, labware_type: str) -> Node:
        protocol = self.move_in_protocol(labware_type)
        return self.add_node(protocol.protocol_name)

    def move_out(self, labware_type: str) -> Node:
        protocol = self.move_out_protocol(labware_type)
        return self.add_node(protocol.protocol_name)

    def store(
        self, labware_type: str, duration: timedelta, store_type: StoreType
    ) -> Node:
        protocol = self.store_protocol(labware_type, duration)
        return self.add_node(protocol.protocol_name, args={"store_type": store_type})

    def check_node(self, node: Node) -> None:
        if node not in self._nodes:
            raise ValueError(f"Node '{node.id}' not found in experiment.")
        protocol = self.get_protocol(node.protocol_name)
        # check args
        for arg_name, arg_type in protocol.args.items():
            if arg_name not in node.args:
                raise ValueError(
                    f"Missing argument '{arg_name}' for node '{node.id}' "
                    f"of protocol '{protocol.protocol_name}'."
                )
            if isinstance(arg_type, list):
                if node.args[arg_name] not in arg_type:
                    raise ValueError(
                        f"Argument '{arg_name}' for node '{node.id}' "
                        f"of protocol '{protocol.protocol_name}' must be in {arg_type}, "
                        f"but got '{node.args[arg_name]}'."
                    )
            else:
                if not isinstance(node.args[arg_name], arg_type):
                    raise ValueError(
                        f"Argument '{arg_name}' for node '{node.id}' "
                        f"of protocol '{protocol.protocol_name}' must be of type {get_args(arg_type)}, "
                        f"but got '{type(node.args[arg_name]).__name__}'."
                    )

    def add_node(self, protocol_name: str, args: dict[str, Any] | None = None) -> Node:
        if args is None:
            args = {}
        node = Node(protocol_name=protocol_name, args=args)
        self._nodes.append(node)
        return node

    def get_node(self, node_id: UUID) -> Node:
        node = next((n for n in self._nodes if n.id == node_id), None)
        if node is None:
            raise ValueError(f"Node '{node_id}' not found in experiment.")
        return node

    def add_edge(
        self, from_node: Node, from_port: str, to_node: Node, to_port: str
    ) -> Edge:
        edge = Edge(
            from_node=from_node.id,
            from_port=from_port,
            to_node=to_node.id,
            to_port=to_port,
        )
        self._edges.append(edge)
        return edge

    def build(self) -> Experiment:
        """Build and return the final Experiment object"""
        for protocol in self._protocols:
            protocol.validate_requirements(
                {lt.name: lt for lt in self._labware_types}, self._reagent_names
            )
        for node in self._nodes:
            self.check_node(node)

        used_from_ports = set()
        used_to_ports = set()
        for edge in self._edges:
            from_node = self.get_node(edge.from_node)
            from_protocol = self.get_protocol(from_node.protocol_name)
            # check if ports exist in protocols
            if edge.from_port not in from_protocol.get_output_ports():
                raise ValueError(
                    f"Port '{edge.from_port}' not found in protocol '{from_protocol.protocol_name}'. "
                    f"Valid ports are: {from_protocol.get_output_ports()}"
                )
            to_node = self.get_node(edge.to_node)
            to_protocol = self.get_protocol(to_node.protocol_name)
            if edge.to_port not in to_protocol.get_input_ports():
                raise ValueError(
                    f"Port '{edge.to_port}' not found in protocol '{to_node.protocol_name}'. "
                    f"Valid ports are: {to_protocol.get_input_ports()}"
                )
            # check for duplicate usage of ports
            if (edge.from_node, edge.from_port) in used_from_ports:
                raise ValueError(
                    f"Duplicate usage of port '{edge.from_port}' "
                    f"on node '{from_protocol.protocol_name}/{edge.from_node}'. "
                )
            if (edge.to_node, edge.to_port) in used_to_ports:
                raise ValueError(
                    f"Duplicate usage of port '{edge.to_port}' "
                    f"on node '{to_protocol.protocol_name}/{edge.to_node}'. "
                )
            used_from_ports.add((edge.from_node, edge.from_port))
            used_to_ports.add((edge.to_node, edge.to_port))
        return Experiment(
            name=self.name,
            reagent_names=self._reagent_names,
            labware_types=self._labware_types,
            protocols=self._protocols,
            nodes=self._nodes,
            edges=self._edges,
        )


if __name__ == "__main__":
    from src.labware import labware_types

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
    exb = (
        Experiment.builder("HEK293A culture")
        .reagent_names("medium", "trypsin", "DMEM", "PBS")
        .labware_types(*labware_types)
        .protocols(medium_change, passage)
    )

    # define experiment workflow using nodes and edges
    move_in_1 = exb.move_in("plate6well")
    medium_change_1 = exb.add_node("medium_change")
    medium_change_2 = exb.add_node("medium_change")
    medium_change_3 = exb.add_node("medium_change")
    passage_1 = exb.add_node("passage")
    move_out_1 = exb.move_out("plate6well")
    store_1 = exb.store("plate6well", timedelta(hours=12), store_type="warm_37")
    store_2 = exb.store("plate6well", timedelta(hours=12), store_type="warm_37")
    store_3 = exb.store("plate6well", timedelta(hours=12), store_type="warm_37")
    store_4 = exb.store("plate6well", timedelta(hours=12), store_type="warm_37")
    exb.add_edge(move_in_1, "labware", medium_change_1, "cell_plate")
    exb.add_edge(medium_change_1, "cell_plate", store_1, "labware")
    exb.add_edge(store_1, "labware", medium_change_2, "cell_plate")
    exb.add_edge(medium_change_2, "cell_plate", store_2, "labware")
    exb.add_edge(store_2, "labware", passage_1, "cell_plate")
    exb.add_edge(passage_1, "new_cell_plate", store_3, "labware")
    exb.add_edge(store_3, "labware", medium_change_3, "cell_plate")
    exb.add_edge(medium_change_3, "cell_plate", move_out_1, "labware")
    experiment = exb.build()

    experiment_json = experiment.model_dump_json(indent=2)
    experiment_reconstructed = Experiment.model_validate_json(experiment_json)
    print(experiment.model_dump_json(indent=2))
