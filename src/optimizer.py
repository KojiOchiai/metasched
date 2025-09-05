from dataclasses import dataclass
from datetime import datetime, timedelta
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


def get_oldest_time(
    protocols: list[protocol.Protocol | protocol.Delay | protocol.Start],
) -> datetime:
    min_time = min(
        (
            p.started_time.timestamp()
            for p in protocols
            if isinstance(p, protocol.Protocol) and p.started_time is not None
        ),
        default=0,
    )
    if min_time == 0:
        return datetime.now()
    return datetime.fromtimestamp(min_time)


def sum_durations(
    protocols: list[protocol.Protocol | protocol.Delay | protocol.Start],
) -> float:
    return sum(
        (
            p.duration.total_seconds()
            for p in protocols
            if isinstance(p, (protocol.Protocol | protocol.Delay))
        ),
        start=0,
    )


class TimeSecondsConverter:
    def __init__(self, start_time: datetime):
        self.start_time = start_time

    def time_to_seconds(self, time: datetime) -> float:
        return (time - self.start_time).total_seconds()

    def seconds_to_time(self, seconds: float) -> datetime:
        return self.start_time + timedelta(seconds=seconds)


def optimize_schedule(start: protocol.Start) -> None:
    span = sum_durations(start.flatten())
    oldest_time = get_oldest_time(start.flatten())
    tsc = TimeSecondsConverter(oldest_time)
    opt_plan = plan_to_opt(start, tsc)

    model = cp_model.CpModel()
    for node in [node for node in opt_plan.flatten() if isinstance(node, Protocol)]:
        node.set_vars(model, int(span))


if __name__ == "__main__":
    s = protocol.Start()
    p1 = protocol.Protocol(name="P1", duration=timedelta(minutes=10))
    p2 = protocol.Protocol(name="P2")
    p3 = protocol.Protocol(name="P3")

    sec5 = protocol.Delay(
        duration=timedelta(seconds=5), from_type=protocol.FromType.START
    )

    s > p1 > p2
    p1 > sec5 > p3

    p1.started_time = datetime.now()
    p2.started_time = datetime.now() + timedelta(minutes=15)
    print(s)
    oldest_time = get_oldest_time(s.flatten())
    print("oldest time: ", oldest_time)
    duration = sum_durations(s.flatten())
    print("total duration: ", duration)
    tsc = TimeSecondsConverter(oldest_time)
    time_in_seconds = tsc.time_to_seconds(p2.started_time)
    print("time in seconds: ", time_in_seconds)
    print("time: ", tsc.seconds_to_time(time_in_seconds))
