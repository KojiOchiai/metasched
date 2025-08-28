from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Union


@dataclass
class Node(ABC):
    name: str

    @abstractmethod
    def add(self, other):
        raise NotImplementedError()

    @abstractmethod
    def __str__(self, indent=0):
        raise NotImplementedError()


@dataclass
class Liquid(Node):
    volume: float = 0.0  # in microliter

    def add(self, other: "Liquid") -> "Liquid":
        raise ValueError("Cannot add to Liquid")

    def __str__(self, indent=0):
        return f"{' ' * indent}{self.name}(liquid, volume={self.volume})"


@dataclass
class Well(Node):
    max_volume: float = 1000.0  # in microliter
    sub_node: list[Liquid] = field(default_factory=list)

    def add(self, other: Liquid) -> "Well":
        if not isinstance(other, Liquid):
            raise ValueError("Can only add Liquid to Well")
        if sum(liq.volume for liq in self.sub_node) + other.volume > self.max_volume:
            raise ValueError("Exceeds maximum volume")
        self.sub_node.append(other)
        return self

    def __str__(self, indent=0):
        base = f"{' ' * indent}{self.name}(well, max_volume={self.max_volume})"
        for child in self.sub_node:
            base += f"\n{child.__str__(indent + 2)}"
        return base


@dataclass
class Jig(Node):
    accept: str = "any"
    sub_node: list["Object"] = field(default_factory=list)

    def add(self, other: "Object") -> "Jig":
        if not isinstance(other, Object):
            raise ValueError("Can only add Object to Jig")
        if self.accept != "any" and self.accept != other.shape:
            raise ValueError(f"Jig only accepts {self.accept}, but got {other.shape}")
        self.sub_node.append(other)
        return self

    def __str__(self, indent=0):
        base = f"{' ' * indent}{self.name}(jig, accept={self.accept})"
        for child in self.sub_node:
            base += f"\n{child.__str__(indent + 2)}"
        return base


@dataclass
class Object(Node):
    shape: str = field(default="unknown")
    sub_node: list[Union[Jig, Well]] = field(default_factory=list)

    def add(self, other: Union[Jig, Well]) -> "Object":
        if not isinstance(other, (Jig, Well)):
            raise ValueError("Can only add Jig or Well to Object")
        self.sub_node.append(other)
        return self

    def __str__(self, indent=0):
        base = f"{' ' * indent}{self.name}(object, shape={self.shape})"
        for child in self.sub_node:
            base += f"\n{child.__str__(indent + 2)}"
        return base


@dataclass
class Root(Node):
    sub_node: list[Object] = field(default_factory=list)

    def add(self, other: Object) -> "Root":
        if not isinstance(other, Object):
            raise ValueError("Can only add Object to Root")
        self.sub_node.append(other)
        return self

    def __str__(self, indent=0):
        base = f"{' ' * indent}{self.name}(root)"
        for child in self.sub_node:
            base += f"\n{child.__str__(indent + 2)}"
        return base


if __name__ == "__main__":
    root = Root(name="Root").add(
        Object(name="TubeRack", shape="tube_rack")
        .add(
            Jig(name="Jig1", accept="50mlTube").add(
                Object(name="50mlTube1", shape="50mlTube").add(
                    Well(name="1", max_volume=5000.0).add(
                        Liquid(name="Water", volume=100.0)
                    )
                )
            )
        )
        .add(
            Jig(name="Jig2", accept="PCRPlate").add(
                Object(name="PCRPlate1", shape="PCRPlate").add(
                    Well(name="1", max_volume=5000.0).add(
                        Liquid(name="Reagent", volume=100.0)
                    )
                )
            )
        )
    )
    print(root)
