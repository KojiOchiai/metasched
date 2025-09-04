from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Union

NodeType = Union["Protocol", "Delay"]


@dataclass
class Node:
    post_node: list[NodeType] = field(default_factory=list)
    pre_node: Union[NodeType, "Start", None] = None

    def __post_init__(self):
        for child in self.post_node:
            child.pre_node = self

    def __gt__(self, other: NodeType | list[NodeType]) -> NodeType:
        if not isinstance(other, list):
            self.add(other)
        elif isinstance(other, list):
            for node in other:
                self.add(node)
        return self.top

    @property
    def top(self):
        if self.pre_node:
            return self.pre_node.top
        return self

    def add(self, other: NodeType) -> None:
        if not isinstance(other, Node):
            return NotImplemented
        if isinstance(other, Protocol):
            if other.name in [
                node.name for node in self.top.flatten() if isinstance(node, Protocol)
            ]:
                raise ValueError(f"Protocol {other.name} already exists")
        if isinstance(self, Delay):
            if isinstance(other, Delay):
                raise ValueError("Cannot connect two Delay nodes")
        self.post_node.append(other)
        other.pre_node = self  # type: ignore

    def to_dict(self):
        return {
            "post_node": [child.to_dict() for child in self.post_node],
        }

    @classmethod
    def from_dict(cls, data: dict):
        post_node = []
        for node_data in data.get("post_node", []):
            if "name" in node_data:
                node = Protocol.from_dict(node_data)
            else:
                node = Delay.from_dict(node_data)
            post_node.append(node)
        return Node(post_node=post_node)

    def flatten(self):
        flat = [self]
        for child in self.post_node:
            flat.extend(child.flatten())
        return flat


@dataclass
class Start(Node):
    def __str__(self, indent=0):
        base = "Start()"
        for child in self.post_node:
            base += f"\n{' ' * (indent + 2)}{child.__str__(indent + 2)}"
        return base

    @classmethod
    def from_dict(cls, data: dict):
        nodes = super().from_dict(data).post_node
        return cls(post_node=nodes)


class FromType(Enum):
    START = "start"
    FINISH = "finish"


@dataclass
class Delay(Node):
    post_node: list["Protocol"] = field(default_factory=list)  # type: ignore
    duration: timedelta = field(default_factory=lambda: timedelta(seconds=0))
    from_type: FromType = FromType.START
    offset: timedelta = field(default_factory=lambda: timedelta(seconds=0))

    def __str__(self, indent=0):
        base = f"Delay(duration={self.duration}, from_type={self.from_type}, offset={self.offset})"
        for child in self.post_node:
            base += f"\n{' ' * (indent + 2)}{child.__str__(indent + 2)}"
        return base

    def to_dict(self):
        nodes = super().to_dict()
        return {
            "duration": self.duration.total_seconds(),
            "from_type": self.from_type.value,
            "offset": self.offset.total_seconds(),
        } | nodes

    @classmethod
    def from_dict(cls, data: dict):
        duration = data.get("duration")
        from_type = data.get("from_type")
        offset = data.get("offset")
        if not isinstance(duration, (int, float)):
            raise ValueError("Duration must be a number representing seconds")
        if not isinstance(offset, (int, float)):
            raise ValueError("Offset must be a number representing seconds")
        duration = timedelta(seconds=duration)
        from_type = FromType(from_type)
        offset = timedelta(seconds=offset)
        nodes = super().from_dict(data).post_node
        return cls(
            duration=duration,
            from_type=from_type,
            offset=offset,
            post_node=nodes,
        )


@dataclass
class Protocol(Node):
    name: str = field(default="")
    duration: timedelta = field(default_factory=lambda: timedelta(seconds=0))

    def __str__(self, indent=0):
        base = f"Protocol(name={self.name}, duration={self.duration})"
        for child in self.post_node:
            base += f"\n{' ' * (indent + 2)}{child.__str__(indent + 2)}"
        return base

    def to_dict(self):
        nodes = super().to_dict()
        return {
            "name": self.name,
            "duration": self.duration.total_seconds(),
        } | nodes

    @classmethod
    def from_dict(cls, data: dict):
        name = data.get("name")
        duration = data.get("duration")
        nodes = super().from_dict(data).post_node
        if name:
            name = str(name)
        else:
            raise ValueError("Protocol must have a name")
        if duration is not None and isinstance(duration, (int, float)):
            duration = float(duration)
        else:
            print(type(duration))
            raise ValueError("Duration must be a number representing seconds")
        return cls(
            name=name,
            duration=timedelta(seconds=duration),
            post_node=nodes,
        )


@dataclass
class StartedProtocol(Protocol):
    scheduled_time: datetime | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None

    def __str__(self, indent=0):
        base = (
            f"StartedProtocol(name={self.name}, duration={self.duration}, "
            f"scheduled_time={self.scheduled_time}, start_time={self.start_time}, "
            f"end_time={self.end_time})"
        )
        for child in self.post_node:
            base += f"\n{' ' * (indent + 2)}{child.__str__(indent + 2)}"
        return base

    @classmethod
    def from_node(cls, node: NodeType):
        if isinstance(node, Protocol):
            self: StartedProtocol | Delay | Start = cls(
                name=node.name,
                duration=node.duration,
                post_node=node.post_node,
            )
        if isinstance(node, Delay):
            self = node
        if isinstance(node, Start):
            self = Start()
        children = [cls.from_node(child) for child in node.post_node]
        self.post_node = children
        return self

    def to_dict(self):
        nodes = super().to_dict()
        return {
            "scheduled_time": self.scheduled_time.isoformat()
            if self.scheduled_time
            else None,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
        } | nodes

    @classmethod
    def from_dict(cls, data: dict):
        name = data.get("name")
        scheduled_time = data.get("scheduled_time")
        start_time = data.get("start_time")
        end_time = data.get("end_time")
        duration = data.get("duration")
        if name:
            name = str(name)
        if duration and isinstance(duration, (int, float)):
            duration = timedelta(seconds=float(duration))
        if scheduled_time:
            scheduled_time = datetime.fromisoformat(scheduled_time)
        else:
            scheduled_time = None
        if start_time:
            start_time = datetime.fromisoformat(start_time)
        else:
            start_time = None
        if end_time:
            end_time = datetime.fromisoformat(end_time)
        else:
            end_time = None
        nodes = super().from_dict(data).post_node
        return cls(
            name=name,
            duration=duration,
            scheduled_time=scheduled_time,
            start_time=start_time,
            end_time=end_time,
            post_node=nodes,
        )


if __name__ == "__main__":
    import json

    s = Start()
    p1 = Protocol(name="P1", duration=timedelta(minutes=10))
    p2 = Protocol(name="P2")
    p3 = Protocol(name="P3")

    sec5 = Delay(duration=-timedelta(seconds=5), from_type=FromType.START)

    s > p1 > p2
    p1 > sec5 > p3

    s_dict = s.to_dict()
    s_json = json.dumps(s_dict)
    s_dict = json.loads(s_json)

    print(s_json)
    print(s_dict)
    print(s)
    s_recon = Start.from_dict(s_dict)
    print(s_recon)
    print(StartedProtocol.from_node(s_recon))
