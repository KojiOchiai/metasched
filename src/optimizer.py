from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Generic, Optional, TypeVar, Union
from uuid import UUID

from ortools.sat.python import cp_model

from src import protocol

model = cp_model.CpModel()

PRE_T = TypeVar("PRE_T", bound=Optional["Node"])
POST_T = TypeVar("POST_T", bound="Node")


@dataclass
class Node(Generic[PRE_T, POST_T]):
    id: UUID
    pre_node: Optional[PRE_T]
    post_node: list[POST_T]

    def __post_init__(self):
        for post_node in self.post_node:
            post_node.pre_node = self

    def flatten(self) -> list["Node[PRE_T, POST_T]"]:
        nodes = [self]
        for child in self.post_node:
            nodes.extend(child.flatten())
        return nodes


@dataclass
class Start(Node[None, Union["Protocol", "Delay"]]):
    pass


@dataclass
class Delay(Node[Union["Start", "Protocol"], "Protocol"]):
    duration: int
    from_type: protocol.FromType
    offset: int
    loss: cp_model.IntVar | None = None

    def set_loss(
        self, model: cp_model.CpModel, max_duration_times: int = 2
    ) -> cp_model.IntVar:
        self.loss = model.NewIntVar(
            0, self.duration * max_duration_times, f"{self.id}_loss"
        )
        for post_node in self.post_node:
            if (
                isinstance(self.pre_node, Protocol)
                and self.pre_node.finish_time is not None
                and isinstance(post_node, Protocol)
                and post_node.start_time is not None
            ):
                diff = post_node.start_time - self.pre_node.finish_time
                target = self.duration + self.offset
                model.Add(self.loss >= diff - target)
                model.Add(self.loss <= diff - target)
        return self.loss


@dataclass
class Protocol(Node[Union["Start", "Delay", "Protocol"], Union["Protocol", "Delay"]]):
    name: str
    duration: int
    started_time: int | None = None
    finished_time: int | None = None
    start_time: cp_model.IntVar | None = None
    finish_time: cp_model.IntVar | None = None
    interval: cp_model.IntervalVar | None = None

    def set_vars(self, model: cp_model.CpModel, max_time: int) -> None:
        self.start_time = model.NewIntVar(0, max_time, f"{self.id}_start_time")
        self.finish_time = model.NewIntVar(0, max_time, f"{self.id}_finish_time")
        if self.started_time is not None:
            model.Add(self.start_time == self.started_time)
            if self.finished_time is not None:
                model.Add(self.finish_time == self.finished_time)
                return
        self.interval = model.NewIntervalVar(
            self.start_time, self.duration, self.finish_time, f"{self.id}_interval"
        )


def protocol_to_opt(
    protocol_node: protocol.Start | protocol.Protocol | protocol.Delay,
    tsc: "TimeSecondsConverter",
) -> Start | Delay | Protocol:
    post_nodes: list[Protocol | Delay] = []
    for post_node in protocol_node.post_node:
        if isinstance(post_node, (protocol.Protocol, protocol.Delay)):
            result = protocol_to_opt(post_node, tsc)
            if isinstance(result, (Protocol, Delay)):
                post_nodes.append(result)
        else:
            raise ValueError("Protocol or Delay expected as post_node")

    if isinstance(protocol_node, protocol.Start):
        return Start(id=protocol_node.id, pre_node=None, post_node=post_nodes)
    elif isinstance(protocol_node, protocol.Protocol):
        started_time = (
            int(tsc.time_to_seconds(protocol_node.started_time))
            if protocol_node.started_time
            else None
        )
        finished_time = (
            int(tsc.time_to_seconds(protocol_node.finished_time))
            if protocol_node.finished_time
            else None
        )
        return Protocol(
            id=protocol_node.id,
            name=protocol_node.name,
            duration=int(protocol_node.duration.total_seconds()),
            started_time=started_time,
            finished_time=finished_time,
            pre_node=None,
            post_node=post_nodes,
        )
    elif isinstance(protocol_node, protocol.Delay):
        for post_opt_node in post_nodes:
            if not isinstance(post_opt_node, Protocol):
                raise ValueError("Protocol expected as post_node")
        return Delay(
            id=protocol_node.id,
            duration=int(protocol_node.duration.total_seconds()),
            from_type=protocol_node.from_type,
            offset=int(protocol_node.offset.total_seconds()),
            pre_node=None,
            post_node=[node for node in post_nodes if isinstance(node, Protocol)],
        )
    else:
        raise ValueError(f"Unknown node type: {type(protocol_node)}")


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
    max_time = int(sum_durations(start.flatten()))
    oldest_time = get_oldest_time(start.flatten())
    tsc = TimeSecondsConverter(oldest_time)
    opt_protocol = protocol_to_opt(start, tsc)

    model = cp_model.CpModel()
    protocol_nodes = [
        node for node in opt_protocol.flatten() if isinstance(node, Protocol)
    ]
    delay_nodes = [node for node in opt_protocol.flatten() if isinstance(node, Delay)]

    intervals = []
    makespan = model.NewIntVar(0, max_time, "makespan")
    for node in protocol_nodes:
        node.set_vars(model, max_time)
        # no overlap
        if node.interval is not None:
            intervals.append(node.interval)
        # finish time
        if node.finish_time is not None:
            model.Add(makespan >= node.finish_time)
    model.AddNoOverlap(intervals)

    # order
    for node in protocol_nodes:
        for post_node in node.post_node:
            if isinstance(post_node, Protocol):
                if node.finish_time is not None and post_node.start_time is not None:
                    model.Add(node.finish_time <= post_node.start_time)

    # delay
    losses = [delay.set_loss(model) for delay in delay_nodes]

    model.minimize(makespan + sum(losses))
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL:
        for node in protocol_nodes:
            if node.start_time is not None and node.finish_time is not None:
                p_node = start.get_node(node.id)
                if isinstance(p_node, protocol.Protocol):
                    p_node.scheduled_time = tsc.seconds_to_time(
                        solver.Value(node.start_time)
                    )
    else:
        raise ValueError("No optimal schedule found.")


if __name__ == "__main__":
    s = protocol.Start()
    p1 = protocol.Protocol(name="P1", duration=timedelta(minutes=10))
    p2 = protocol.Protocol(name="P2", duration=timedelta(seconds=2))
    p3 = protocol.Protocol(name="P3", duration=timedelta(seconds=2))

    sec5 = protocol.Delay(
        duration=timedelta(seconds=5), from_type=protocol.FromType.START
    )

    s > p1 > [p2, sec5 > p3]

    p1.started_time = datetime.now()
    p1.finished_time = p1.started_time + timedelta(minutes=10, seconds=1)
    p2.started_time = datetime.now() + timedelta(minutes=10, seconds=2)
    print(s)
    oldest_time = get_oldest_time(s.flatten())
    print("oldest time: ", oldest_time)
    duration = sum_durations(s.flatten())
    print("total duration: ", duration)
    tsc = TimeSecondsConverter(oldest_time)
    time_in_seconds = tsc.time_to_seconds(p1.started_time)
    print("time in seconds: ", time_in_seconds)
    print("time: ", tsc.seconds_to_time(time_in_seconds))
    print("---- to opt ----")
    optimize_schedule(s)
    print(s)
