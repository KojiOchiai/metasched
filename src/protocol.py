from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Generic, Optional, Self, TypeVar, Union
from uuid import UUID, uuid4

PRE_T = TypeVar("PRE_T", bound=Optional["Node"])
POST_T = TypeVar("POST_T", bound="Node")


class NodeType(Enum):
    START = "start"
    DELAY = "delay"
    PROTOCOL = "protocol"


@dataclass
class Node(Generic[PRE_T, POST_T]):
    node_type: NodeType
    id: UUID = field(default_factory=uuid4)
    pre_node: Optional[PRE_T] = None
    post_node: list[POST_T] = field(default_factory=list)

    def __post_init__(self):
        for child in self.post_node:
            if self.is_recursive(child):
                raise ValueError("Cannot add a recursive node")
            child.pre_node = self

    def __gt__(self, other: POST_T | list[POST_T]) -> Self:
        if not isinstance(other, list):
            self.add(other)
        elif isinstance(other, list):
            for node in other:
                self.add(node)
        return self.top

    def is_recursive(self, other: Self) -> bool:
        return other.id in [node.id for node in self.top.flatten()]

    @property
    def top(self) -> Self:
        if self.pre_node is not None:
            return self.pre_node.top
        return self

    def add(self, other: POST_T) -> None:
        if self.is_recursive(other):
            raise ValueError("Cannot add a recursive node")
        self.post_node.append(other)
        other.pre_node = self

    @abstractmethod
    def to_dict(self):
        return {
            "id": str(self.id),
            "node_type": self.node_type.value,
            "post_node": [child.to_dict() for child in self.post_node],
        }

    @abstractmethod
    def from_dict(cls, data: dict) -> Self:
        raise NotImplementedError

    def flatten(self):
        flat = [self]
        for child in self.post_node:
            flat.extend(child.flatten())
        return flat

    def get_node(self, id: UUID):
        if self.id == id:
            return self
        for child in self.post_node:
            result = child.get_node(id)
            if result is not None:
                return result
        return None


@dataclass
class Start(Node[None, Union["Protocol", "Delay"]]):
    requested_start_time: datetime = field(default_factory=datetime.now)
    node_type: NodeType = field(default=NodeType.START)

    def __str__(self, indent=0):
        base = f"Start(requested_start_time={self.requested_start_time})"
        for child in self.post_node:
            base += f"\n{' ' * (indent + 2)}{child.__str__(indent + 2)}"
        return base

    def to_dict(self):
        return super().to_dict()

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        node_type = data.get("node_type")
        if node_type is None or NodeType(node_type) != NodeType.START:
            raise ValueError("Invalid node_type for Start node")
        return cls()


class FromType(Enum):
    START = "start"
    FINISH = "finish"


@dataclass
class Delay(Node["Protocol", "Protocol"]):
    node_type: NodeType = field(default=NodeType.DELAY)
    duration: timedelta = field(default_factory=lambda: timedelta(seconds=0))
    from_type: FromType = FromType.START
    offset: timedelta = field(default_factory=lambda: timedelta(seconds=0))

    def __str__(self, indent=0):
        base = f"Delay(duration={self.duration}, from_type={self.from_type}, offset={self.offset})"
        for child in self.post_node:
            base += f"\n{' ' * (indent + 2)}{child.__str__(indent + 2)}"
        return base

    def to_dict(self):
        return {
            "duration": self.duration.total_seconds(),
            "from_type": self.from_type.name,
            "offset": self.offset.total_seconds(),
            **super().to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        node_type = data.get("node_type")
        if node_type is None or NodeType(node_type) != NodeType.DELAY:
            raise ValueError("Invalid node_type for Delay node")
        id = data.get("id")
        if id is None:
            raise ValueError("Missing id for Delay node")
        id = UUID(id)
        duration = data.get("duration")
        if duration is None:
            raise ValueError("Missing duration for Delay node")
        offset = data.get("offset")
        if offset is None:
            raise ValueError("Missing offset for Delay node")
        from_type = data.get("from_type")
        if from_type is None:
            raise ValueError("Missing from_type for Delay node")
        return cls(
            id=id,
            duration=timedelta(seconds=duration),
            from_type=FromType[from_type],
            offset=timedelta(seconds=offset),
        )


@dataclass
class Protocol(Node[Union["Protocol", "Start", "Delay"], Union["Protocol", "Delay"]]):
    node_type: NodeType = field(default=NodeType.PROTOCOL)
    name: str = field(default="")
    duration: timedelta = field(default_factory=lambda: timedelta(seconds=0))
    scheduled_time: datetime | None = None
    started_time: datetime | None = None
    finished_time: datetime | None = None

    def __str__(self, indent=0):
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

    def to_dict(self):
        scheduled_time = (
            self.scheduled_time.timestamp() if self.scheduled_time else None
        )
        started_time = self.started_time.timestamp() if self.started_time else None
        finished_time = self.finished_time.timestamp() if self.finished_time else None
        return {
            "name": self.name,
            "id": str(self.id),
            "duration": self.duration.total_seconds(),
            "scheduled_time": scheduled_time,
            "started_time": started_time,
            "finished_time": finished_time,
            **super().to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        node_type = data.get("node_type")
        if node_type is None or NodeType(node_type) != NodeType.PROTOCOL:
            raise ValueError("Invalid node_type for Protocol node")
        id = data.get("id")
        if id is None:
            raise ValueError("Missing id for Protocol node")
        id = UUID(id)
        name = data.get("name")
        if name is None:
            raise ValueError("Missing name for Protocol node")
        duration = data.get("duration")
        if duration is None:
            raise ValueError("Missing duration for Protocol node")
        scheduled_time = data.get("scheduled_time")
        started_time = data.get("started_time")
        finished_time = data.get("finished_time")
        if scheduled_time is not None:
            scheduled_time = datetime.fromtimestamp(scheduled_time)
        if started_time is not None:
            started_time = datetime.fromtimestamp(started_time)
        if finished_time is not None:
            finished_time = datetime.fromtimestamp(finished_time)
        return cls(
            name=name,
            id=id,
            duration=timedelta(seconds=duration),
            scheduled_time=scheduled_time,
            started_time=started_time,
            finished_time=finished_time,
        )


def protocol_from_dict(data: dict) -> Start | Delay | Protocol:
    # get node_type
    node_type = data.get("node_type")
    if node_type is None:
        raise ValueError("Missing node_type")
    node_type = NodeType(node_type)

    # get post_node
    post_nodes = data.get("post_node")
    if post_nodes is None:
        raise ValueError("Missing post_node")
    post_nodes = [protocol_from_dict(child) for child in post_nodes]

    # parse tree
    current_node: Union[Start, Delay, Protocol]
    if node_type == NodeType.START:  # start
        current_node = Start.from_dict(data)
        for post_node in post_nodes:
            if not (type(post_node) is Protocol or type(post_node) is Delay):
                raise ValueError("Invalid post_node type")
            current_node.add(post_node)
    elif node_type == NodeType.DELAY:  # delay
        current_node = Delay.from_dict(data)
        for post_node in post_nodes:
            if type(post_node) is not Protocol:
                raise ValueError("Invalid post_node type")
            current_node.add(post_node)
    elif node_type == NodeType.PROTOCOL:  # protocol
        current_node = Protocol.from_dict(data)
        for post_node in post_nodes:
            if not (type(post_node) is Protocol or type(post_node) is Delay):
                raise ValueError("Invalid post_node type")
            current_node.add(post_node)
    else:
        raise ValueError(f"Unknown node type: {node_type}")
    return current_node


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


if __name__ == "__main__":
    import json

    s = Start()
    p1 = Protocol(name="P1", duration=timedelta(minutes=10))
    p2 = Protocol(name="P2")
    p3 = Protocol(name="P3")

    sec5 = Delay(duration=timedelta(seconds=5), from_type=FromType.START)

    s > p1 > p2
    p1 > sec5 > p3

    s_dict = s.to_dict()
    s_json = json.dumps(s_dict)
    s_dict = json.loads(s_json)

    print(s_json)
    print(s_dict)
    print(s)
    s_recon = protocol_from_dict(s_dict)
    print(s_recon)
    s_recon.post_node[0].started_time = datetime.now()  # type: ignore
    print(s_recon)
    print(protocol_from_dict(s_recon.to_dict()))
