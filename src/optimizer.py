from dataclasses import dataclass
from uuid import UUID

from ortools.sat.python import cp_model

from src import protocol

model = cp_model.CpModel()


@dataclass
class Node:
    id: UUID
    post_node: list["Node"]


@dataclass
class Start(Node):
    start_time: int


@dataclass
class Delay(Node):
    duration: int
    from_type: protocol.FromType
    offset: int


@dataclass
class Protocol(Node):
    name: str
    duration: int
    started_time: cp_model.IntVar | None = None
    finished_time: cp_model.IntVar | None = None
    interval: cp_model.IntervalVar | None = None

    def set_vars(self, model: cp_model.CpModel, max_time: int) -> None:
        self.started_time = model.NewIntVar(0, max_time, f"{self.id}_started_time")
        self.finished_time = model.NewIntVar(0, max_time, f"{self.id}_finished_time")
        self.interval = model.NewIntervalVar(
            self.started_time, self.duration, self.finished_time, f"{self.id}_interval"
        )
