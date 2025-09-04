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
    started_at: cp_model.IntVar | None = None
    finished_at: cp_model.IntVar | None = None
    interval: cp_model.IntervalVar | None = None

    def set_vars(self, model: cp_model.CpModel, max_time: int) -> None:
        self.started_at = model.NewIntVar(0, max_time, f"{self.id}_started_at")
        self.finished_at = model.NewIntVar(0, max_time, f"{self.id}_finished_at")
        self.interval = model.NewIntervalVar(
            self.started_at, self.duration, self.finished_at, f"{self.id}_interval"
        )
