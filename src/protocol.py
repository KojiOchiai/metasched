from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from typing import Union

NodeType = Union["Protocol", "Delay"]


@dataclass
class Node:
    post_node: list[NodeType] = field(default_factory=list)

    def __gt__(self, other: NodeType | list[NodeType]) -> "Node":
        if not isinstance(other, list):
            self.add(other)
        elif isinstance(other, list):
            for node in other:
                self.add(node)
        return self

    def add(self, other: Union["Protocol", "Delay"]) -> "Node":
        if not isinstance(other, Node):
            return NotImplemented
        if isinstance(other, Protocol):
            if other.name in [
                node.name for node in self.flatten() if isinstance(node, Protocol)
            ]:
                raise ValueError(f"Protocol {other.name} already exists")
        if isinstance(self, Delay):
            if isinstance(other, Delay):
                raise ValueError("Cannot connect two Delay nodes")
        self.post_node.append(other)
        return other

    def to_dict(self):
        return {
            "post_node": [child.to_dict() for child in self.post_node],
        }

    def flatten(self):
        flat = [self]
        for child in self.post_node:
            flat.extend(child.flatten())
        return flat


class Start(Node):
    def __str__(self, indent=0):
        base = "Start()"
        for child in self.post_node:
            base += f"\n{' ' * (indent + 2)}{child.__str__(indent + 2)}"
        return base

    @classmethod
    def from_dict(cls, data: dict):
        nodes = []
        for node in data.get("post_node", []):
            if "duration" in node:
                node = Delay.from_dict(node)
                print(node)
            elif "name" in node:
                node = Protocol.from_dict(node)
            nodes.append(node)
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
        duration = data.get("duration", timedelta(seconds=0))
        from_type = data.get("from_type", FromType.START)
        offset = data.get("offset", timedelta(seconds=0))
        if not isinstance(duration, (int, float)):
            raise ValueError("Duration must be a number representing seconds")
        if not isinstance(offset, (int, float)):
            raise ValueError("Offset must be a number representing seconds")
        duration = timedelta(seconds=duration)
        from_type = FromType(from_type)
        offset = timedelta(seconds=offset)
        nodes = []
        for node in data.get("post_node", []):
            if "duration" in node:
                node = Delay.from_dict(node)
            elif "name" in node:
                node = Protocol.from_dict(node)
            nodes.append(node)
        return cls(
            duration=duration,
            from_type=from_type,
            offset=offset,
            post_node=nodes,
        )


@dataclass
class Protocol(Node):
    name: str | None = None

    def __str__(self, indent=0):
        base = f"Protocol(name={self.name})"
        for child in self.post_node:
            base += f"\n{' ' * (indent + 2)}{child.__str__(indent + 2)}"
        return base

    def to_dict(self):
        nodes = super().to_dict()
        return {
            "name": self.name,
        } | nodes

    @classmethod
    def from_dict(cls, data: dict):
        name = data.get("name", None)
        nodes = []
        for node in data.get("post_node", []):
            if "duration" in node:
                node = Delay.from_dict(node)
            elif "name" in node:
                node = Protocol.from_dict(node)
            nodes.append(node)
        return cls(
            name=name,
            post_node=nodes,
        )


if __name__ == "__main__":
    import json

    s = Start()
    p1 = Protocol(name="P1")
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
    print(Start.from_dict(s_dict))
