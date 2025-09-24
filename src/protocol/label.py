from dataclasses import dataclass, field
from typing import Literal

StoreType = Literal["cold_4", "cold_20", "cold_80", "ambient", "warm_30", "warm_37"]


@dataclass
class Label:
    name: str
    aliases: list[str] = field(default_factory=list)


class LabelStorage:
    _labels: list[Label] = field(default_factory=list)

    def is_label_name(self, name: str) -> bool:
        return any(
            name == label.name or name in label.aliases for label in self._labels
        )

    def add_label(self, name: str, aliases: list[str] | None = None) -> None:
        if aliases is None:
            aliases = []
        if self.is_label_name(name):
            raise ValueError(f"Liquid name '{name}' already exists.")
        self._labels.append(Label(name=name, aliases=aliases))

    def remove_label_name(self, name: str) -> None:
        self._labels = [label for label in self._labels if label.name != name]
