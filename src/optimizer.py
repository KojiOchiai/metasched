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
