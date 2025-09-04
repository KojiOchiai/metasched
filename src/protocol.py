from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Generic, Optional, Self, TypeVar, Union

PRE_T = TypeVar("PRE_T", bound=Optional["Node"])
POST_T = TypeVar("POST_T", bound="Node")


class NodeType(Enum):
    PLAN_START = "plan_start"
    DELAY = "delay"
    PROTOCOL = "protocol"
    SCHEDULE_START = "schedule_start"
    STARTED_PROTOCOL = "started_protocol"


@dataclass
class Node(Generic[PRE_T, POST_T]):
    node_type: NodeType
    pre_node: Optional[PRE_T] = None
    post_node: list[POST_T] = field(default_factory=list)

    def __post_init__(self):
        for child in self.post_node:
            child.pre_node = self

    def __gt__(self, other: POST_T | list[POST_T]) -> Self:
        if not isinstance(other, list):
            self.add(other)
        elif isinstance(other, list):
            for node in other:
                self.add(node)
        return self.top

    @property
    def top(self) -> Self:
        if self.pre_node is not None:
            return self.pre_node.top
        return self

    def add(self, other: POST_T) -> None:
        self.post_node.append(other)
        other.pre_node = self

    @abstractmethod
    def to_dict(self):
        return {
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


@dataclass
class Start(Node[None, Union["Protocol", "Delay"]]):
    node_type: NodeType = field(default=NodeType.PLAN_START)

    def __str__(self, indent=0):
        base = "Start()"
        for child in self.post_node:
            base += f"\n{' ' * (indent + 2)}{child.__str__(indent + 2)}"
        return base

    def to_dict(self):
        return super().to_dict()

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        return cls()


@dataclass
class ScheduleStart(Node[None, Union["StartedProtocol", "Delay"]]):
    node_type: NodeType = field(default=NodeType.SCHEDULE_START)
    start_time: datetime | None = None

    def __str__(self, indent=0):
        base = f"Schedule(start_time={self.start_time})"
        for child in self.post_node:
            base += f"\n{' ' * (indent + 2)}{child.__str__(indent + 2)}"
        return base

    def to_dict(self):
        return {"start_time": self.start_time, **super().to_dict()}

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        node_type = data.get("node_type")
        if node_type is None or NodeType(node_type) != NodeType.SCHEDULE_START:
            raise ValueError("Invalid node_type for ScheduleStart node")
        start_time = data.get("start_time")
        if start_time is not None:
            start_time = datetime.fromtimestamp(start_time)
        return cls(
            start_time=start_time,
        )


class FromType(Enum):
    START = "start"
    FINISH = "finish"


@dataclass
class Delay(Node[Union["Protocol", "Start"], Union["Protocol"]]):
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
        duration = data.get("duration")
        offset = data.get("offset")
        from_type = data.get("from_type")
        if duration is None:
            raise ValueError("Missing duration for Delay node")
        if offset is None:
            raise ValueError("Missing offset for Delay node")
        if from_type is None:
            raise ValueError("Missing from_type for Delay node")
        return cls(
            duration=timedelta(seconds=duration),
            from_type=FromType[from_type],
            offset=timedelta(seconds=offset),
        )


@dataclass
class Protocol(Node[Union["Protocol", "Start", "Delay"], Union["Protocol", "Delay"]]):
    node_type: NodeType = field(default=NodeType.PROTOCOL)
    name: str = field(default="")
    duration: timedelta = field(default_factory=lambda: timedelta(seconds=0))

    def __str__(self, indent=0):
        base = f"Protocol(name={self.name}, duration={self.duration})"
        for child in self.post_node:
            base += f"\n{' ' * (indent + 2)}{child.__str__(indent + 2)}"
        return base

    def to_dict(self):
        return {
            "name": self.name,
            "duration": self.duration.total_seconds(),
            **super().to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        node_type = data.get("node_type")
        if node_type is None or NodeType(node_type) != NodeType.PROTOCOL:
            raise ValueError("Invalid node_type for Protocol node")
        name = data.get("name")
        duration = data.get("duration")
        if name is None:
            raise ValueError("Missing name for Protocol node")
        if duration is None:
            raise ValueError("Missing duration for Protocol node")
        return cls(
            name=name,
            duration=timedelta(seconds=duration),
        )


@dataclass
class StartedProtocol(Protocol):
    node_type: NodeType = field(default=NodeType.STARTED_PROTOCOL)
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

    def to_dict(self):
        return {
            "scheduled_time": self.scheduled_time,
            "start_time": self.start_time,
            "end_time": self.end_time,
            **super().to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        node_type = data.get("node_type")
        if node_type is None or NodeType(node_type) != NodeType.STARTED_PROTOCOL:
            raise ValueError("Invalid node_type for StartedProtocol node")
        name = data.get("name")
        duration = data.get("duration")
        scheduled_time = data.get("scheduled_time")
        start_time = data.get("start_time")
        end_time = data.get("end_time")
        if name is None:
            raise ValueError("Missing name for StartedProtocol node")
        if duration is None:
            raise ValueError("Missing duration for StartedProtocol node")
        if scheduled_time is not None:
            scheduled_time = datetime.fromtimestamp(scheduled_time)
        if start_time is not None:
            start_time = datetime.fromtimestamp(start_time)
        if end_time is not None:
            end_time = datetime.fromtimestamp(end_time)
        return cls(
            name=name,
            duration=timedelta(seconds=duration),
            scheduled_time=scheduled_time,
            start_time=start_time,
            end_time=end_time,
        )

    @classmethod
    def from_protocol(cls, protocol: "Protocol") -> Self:
        return cls(
            name=protocol.name,
            duration=protocol.duration,
        )


def plan2schedule(
    node: Union["Start", "Protocol", "Delay"],
) -> Union["ScheduleStart", "StartedProtocol", "Delay"]:
    post_nodes = [plan2schedule(p_node) for p_node in node.post_node]
    current_node: Union["ScheduleStart", "StartedProtocol", "Delay"]
    if type(node) is Start:
        current_node = ScheduleStart()
        for post_node in post_nodes:
            if not (type(post_node) is StartedProtocol or type(post_node) is Delay):
                raise ValueError("Invalid post_node type")
            current_node.add(post_node)
    elif type(node) is Protocol:
        current_node = StartedProtocol.from_protocol(node)
        for post_node in post_nodes:
            if not (type(post_node) is StartedProtocol or type(post_node) is Delay):
                raise ValueError("Invalid post_node type")
            current_node.add(post_node)
    elif type(node) is Delay:
        current_node = node
        for post_node in post_nodes:
            if not (type(post_node) is StartedProtocol or type(post_node) is Delay):
                raise ValueError("Invalid post_node type")
            current_node.add(post_node)
    return current_node


def plan_from_dict(data: dict) -> Start | Delay | Protocol:
    # get node_type
    node_type = data.get("node_type")
    if node_type is None:
        raise ValueError("Missing node_type")
    node_type = NodeType(node_type)

    # get post_node
    post_nodes = data.get("post_node")
    if post_nodes is None:
        raise ValueError("Missing post_node")
    post_nodes = [plan_from_dict(child) for child in post_nodes]

    # parse tree
    current_node: Union[Start, Delay, Protocol, ScheduleStart, StartedProtocol]
    if node_type == NodeType.PLAN_START:  # start
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


def schedule_from_dict(
    data: dict,
) -> ScheduleStart | Delay | StartedProtocol:
    # get node_type
    node_type = data.get("node_type")
    if node_type is None:
        raise ValueError("Missing node_type")
    node_type = NodeType(node_type)

    # get post_node
    post_nodes = data.get("post_node")
    if post_nodes is None:
        raise ValueError("Missing post_node")
    post_nodes = [schedule_from_dict(child) for child in post_nodes]

    # parse tree
    current_node: Union[Start, Delay, Protocol, ScheduleStart, StartedProtocol]
    if node_type == NodeType.SCHEDULE_START:  # schedule
        current_node = ScheduleStart.from_dict(data)
        for post_node in post_nodes:
            if not (type(post_node) is StartedProtocol or type(post_node) is Delay):
                raise ValueError("Invalid post_node type")
            current_node.add(post_node)
    elif node_type == NodeType.DELAY:  # delay
        current_node = Delay.from_dict(data)
        for post_node in post_nodes:
            if type(post_node) is not Protocol:
                raise ValueError("Invalid post_node type")
            current_node.add(post_node)
    elif node_type == NodeType.STARTED_PROTOCOL:  # started protocol
        current_node = StartedProtocol.from_dict(data)
        for post_node in post_nodes:
            if not (type(post_node) is StartedProtocol or type(post_node) is Delay):
                raise ValueError("Invalid post_node type")
            current_node.add(post_node)
    else:
        raise ValueError(f"Unknown node type: {node_type}")
    return current_node


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
    s_recon = plan_from_dict(s_dict)
    print(s_recon)
    started_protocol = plan2schedule(s_recon)
    print(started_protocol)
    started_protocol.post_node[0].start_time = datetime.now()  # type: ignore
    print(started_protocol)
    print(schedule_from_dict(started_protocol.to_dict()))
