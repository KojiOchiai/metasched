import importlib
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional, Self
from uuid import UUID, uuid4

from pydantic import BaseModel, Discriminator, Field, Tag, TypeAdapter, model_validator


class NodeType(Enum):
    START = "start"
    DELAY = "delay"
    PROTOCOL = "protocol"


class FromType(Enum):
    START = "start"
    FINISH = "finish"


class Node(BaseModel):
    node_type: NodeType
    id: UUID = Field(default_factory=uuid4)
    pre_node: Optional["Node"] = Field(default=None, exclude=True, repr=False)
    post_node: list["NodeUnion"] = Field(default_factory=list)

    @model_validator(mode="after")
    def _link_children(self) -> Self:
        for child in self.post_node:
            child.pre_node = self
        return self

    def __gt__(self, other: "Node | list[Node]") -> Self:
        if not isinstance(other, list):
            self.add(other)
        elif isinstance(other, list):
            for node in other:
                self.add(node)
        return self.top

    def is_recursive(self, other: "Node") -> bool:
        return other.id in [node.id for node in self.top.flatten()]

    @property
    def top(self) -> Self:
        if self.pre_node is not None:
            return self.pre_node.top
        return self

    def add(self, other: "Node") -> None:
        if self.is_recursive(other):
            raise ValueError("Cannot add a recursive node")
        self.post_node.append(other)
        other.pre_node = self

    def flatten(self) -> list["Node"]:
        flat: list[Node] = [self]
        for child in self.post_node:
            flat.extend(child.flatten())
        return flat

    def get_node(self, id: UUID) -> Optional["Node"]:
        if self.id == id:
            return self
        for child in self.post_node:
            result = child.get_node(id)
            if result is not None:
                return result
        return None


class Start(Node):
    node_type: NodeType = NodeType.START

    def __str__(self, indent: int = 0) -> str:
        base = "Start()"
        for child in self.post_node:
            base += f"\n{' ' * (indent + 2)}{child.__str__(indent + 2)}"
        return base


class Delay(Node):
    node_type: NodeType = NodeType.DELAY
    duration: timedelta = Field(default_factory=lambda: timedelta(seconds=0))
    from_type: FromType = FromType.START
    offset: timedelta = Field(default_factory=lambda: timedelta(seconds=0))

    def __str__(self, indent: int = 0) -> str:
        base = f"Delay(duration={self.duration}, from_type={self.from_type}, offset={self.offset})"
        for child in self.post_node:
            base += f"\n{' ' * (indent + 2)}{child.__str__(indent + 2)}"
        return base


class Protocol(Node):
    node_type: NodeType = NodeType.PROTOCOL
    name: str = ""
    duration: timedelta = Field(default_factory=lambda: timedelta(seconds=0))
    scheduled_time: datetime | None = None
    started_time: datetime | None = None
    finished_time: datetime | None = None

    def __str__(self, indent: int = 0) -> str:
        base = (
            f"Protocol(name={self.name}"
            f", duration={self.duration}"
            f", scheduled_time={self.scheduled_time}"
            f", started_time={self.started_time}"
            f", finished_time={self.finished_time})"
        )
        for child in self.post_node:
            base += f"\n{' ' * (indent + 2)}{child.__str__(indent + 2)}"
        return base


def _node_discriminator(v: dict | Node) -> str:
    if isinstance(v, dict):
        return v.get("node_type", "")
    return v.node_type.value


NodeUnion = Annotated[
    Annotated[Start, Tag("start")]
    | Annotated[Delay, Tag("delay")]
    | Annotated[Protocol, Tag("protocol")],
    Discriminator(_node_discriminator),
]

# Rebuild models to resolve forward references to NodeUnion
Node.model_rebuild()
Start.model_rebuild()
Delay.model_rebuild()
Protocol.model_rebuild()

_node_adapter: TypeAdapter[Start | Delay | Protocol] = TypeAdapter(NodeUnion)


def protocol_from_dict(data: dict) -> Start | Delay | Protocol:
    return _node_adapter.validate_python(data)


def format_protocol(start: Start) -> str:
    protocol_nodes: list[Protocol] = [
        node for node in start.flatten() if type(node) is Protocol
    ]
    sorted_nodes = sorted(
        protocol_nodes, key=lambda x: x.scheduled_time or datetime.max
    )

    start_time = sorted_nodes[0].scheduled_time
    finish_time = sorted_nodes[-1].scheduled_time
    last_duration = sorted_nodes[-1].duration
    if start_time is None or finish_time is None or last_duration is None:
        raise ValueError("No scheduled times found.")
    total_duration = finish_time - start_time + last_duration

    txt = f"Schedule: (total duration: {total_duration})\n"
    for node in sorted_nodes:
        if node.scheduled_time is not None:
            state = ""
            if node.started_time is not None:
                started_time = node.started_time
                state = "[Started]"
            else:
                started_time = node.scheduled_time
            if node.finished_time is not None:
                finished_time = node.finished_time
                state = "[Done]"
            else:
                finished_time = node.scheduled_time + node.duration
            duration = finished_time - node.scheduled_time
            txt += (
                f" - {node.name}: "
                f"[{timedelta(seconds=round((started_time - start_time).total_seconds()))}] "
                f"{started_time.strftime('%Y-%m-%d %H:%M:%S')} ~ "
                f"{finished_time.strftime('%Y-%m-%d %H:%M:%S')}"
                f" (Duration: {timedelta(seconds=round(duration.total_seconds()))})"
                f" {state}\n"
            )
    delay_nodes: list[Delay] = [
        node for node in start.flatten() if isinstance(node, Delay)
    ]
    txt += "Delay:\n"
    for delay in delay_nodes:
        pre_node = delay.pre_node
        if pre_node is None:
            continue
        for post_node in delay.post_node:
            if post_node.scheduled_time is None:
                continue
            if pre_node.finished_time is not None:
                pre_node_finish = pre_node.finished_time
            elif pre_node.scheduled_time is not None:
                pre_node_finish = pre_node.scheduled_time + pre_node.duration
            true_duration = post_node.scheduled_time - pre_node_finish
            txt += (
                f" - {pre_node.name}"
                " -- "
                f"{pre_node_finish.strftime('%Y-%m-%d %H:%M:%S')} "
                f"~ {post_node.scheduled_time.strftime('%Y-%m-%d %H:%M:%S')}"
                f" | {true_duration}(target: {delay.duration + delay.offset})"
                " -> "
                f"{post_node.name}\n"
            )
    return txt


def load_protocol(protocolfile: Path) -> Start:
    """Load a protocol from a Python file and return the Start object."""
    protocol_module = importlib.import_module(
        str(protocolfile).replace("/", ".").replace(".py", "")
    )
    protocol: Start | None = next(
        (obj for obj in vars(protocol_module).values() if isinstance(obj, Start)),
        None,
    )
    if protocol is None:
        raise ValueError(
            f"Protocol type 'Start' not found in the module '{protocolfile}'."
        )
    return protocol


if __name__ == "__main__":
    import json

    s = Start()
    p1 = Protocol(name="P1", duration=timedelta(minutes=10))
    p2 = Protocol(name="P2")
    p3 = Protocol(name="P3")

    sec5 = Delay(duration=timedelta(seconds=5), from_type=FromType.START)

    s > p1 > p2
    p1 > sec5 > p3

    s_dict = s.model_dump(mode="json")
    s_json = json.dumps(s_dict)
    s_dict = json.loads(s_json)

    print(s_json)
    print(s_dict)
    print(s)
    s_recon = protocol_from_dict(s_dict)
    print(s_recon)
    s_recon.post_node[0].started_time = datetime.now()  # type: ignore
    print(s_recon)
    print(protocol_from_dict(s_recon.model_dump(mode="json")))
