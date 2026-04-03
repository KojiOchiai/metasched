from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from ortools.sat.python import cp_model

from src import protocol

STATUS_STR = {
    cp_model.OPTIMAL: "OPTIMAL",
    cp_model.FEASIBLE: "FEASIBLE",
    cp_model.INFEASIBLE: "INFEASIBLE",
    cp_model.MODEL_INVALID: "MODEL_INVALID",
    cp_model.UNKNOWN: "UNKNOWN",
}


@dataclass
class ProtocolVars:
    duration_s: int
    started_s: int | None = None
    finished_s: int | None = None
    start_time: cp_model.IntVar | None = None
    finish_time: cp_model.IntVar | None = None
    interval: cp_model.IntervalVar | None = None


@dataclass
class DelayVars:
    duration_s: int
    offset_s: int
    loss: cp_model.IntVar | None = None


def _create_protocol_vars(
    model: cp_model.CpModel, pv: ProtocolVars, node_id: UUID, max_time: int
) -> None:
    pv.start_time = model.NewIntVar(0, max_time, f"{node_id}_start_time")
    pv.finish_time = model.NewIntVar(0, max_time, f"{node_id}_finish_time")
    if pv.started_s is not None:
        model.Add(pv.start_time == pv.started_s)
        if pv.finished_s is not None:
            model.Add(pv.finish_time == pv.finished_s)
            pv.interval = model.NewIntervalVar(
                pv.start_time,
                pv.finished_s - pv.started_s,
                pv.finish_time,
                f"{node_id}_interval",
            )
            return
    pv.interval = model.NewIntervalVar(
        pv.start_time, pv.duration_s, pv.finish_time, f"{node_id}_interval"
    )


def _create_delay_loss(
    model: cp_model.CpModel,
    delay_node: protocol.Delay,
    dv: DelayVars,
    pvars: dict[UUID, ProtocolVars],
    max_time: int = 0,
) -> cp_model.IntVar:
    dv.loss = model.NewIntVar(0, max_time, f"{delay_node.id}_loss")
    pre = delay_node.pre_node
    if isinstance(pre, protocol.Protocol) and pre.id in pvars:
        pre_pv = pvars[pre.id]
        for post_node in delay_node.post_node:
            if isinstance(post_node, protocol.Protocol) and post_node.id in pvars:
                post_pv = pvars[post_node.id]
                if pre_pv.finish_time is not None and post_pv.start_time is not None:
                    diff = post_pv.start_time - pre_pv.finish_time
                    target = dv.duration_s + dv.offset_s
                    model.Add(dv.loss >= diff - target)
                    model.Add(dv.loss >= target - diff)
    return dv.loss


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


class Optimizer:
    def __init__(
        self,
        buffer_seconds: int = 0,
        time_loss_weight: int = 100,
        max_solve_time: int = 3,
    ) -> None:
        self.buffer_seconds = buffer_seconds
        self.time_loss_weight = time_loss_weight
        self.max_solve_time = max_solve_time

    def optimize_schedule(self, start: protocol.Start) -> str:
        nodes = start.flatten()
        oldest_time = get_oldest_time(nodes)
        elapsed_s = int((datetime.now() - oldest_time).total_seconds())
        max_time = (
            elapsed_s
            + int(sum_durations(nodes))
            + len(nodes) * self.buffer_seconds
        )
        tsc = TimeSecondsConverter(oldest_time)

        # Build flat lookup dicts from domain tree
        pvars: dict[UUID, ProtocolVars] = {}
        dvars: dict[UUID, DelayVars] = {}
        for node in nodes:
            if isinstance(node, protocol.Protocol):
                started_s = (
                    int(tsc.time_to_seconds(node.started_time))
                    if node.started_time
                    else None
                )
                finished_s = (
                    int(tsc.time_to_seconds(node.finished_time))
                    if node.finished_time
                    else None
                )
                pvars[node.id] = ProtocolVars(
                    duration_s=int(node.duration.total_seconds() + self.buffer_seconds),
                    started_s=started_s,
                    finished_s=finished_s,
                )
            elif isinstance(node, protocol.Delay):
                total_s = node.duration.total_seconds()
                if total_s < self.buffer_seconds:
                    raise ValueError(
                        f"Delay duration {total_s} is shorter than buffer {self.buffer_seconds}"
                    )
                dvars[node.id] = DelayVars(
                    duration_s=int(total_s - self.buffer_seconds),
                    offset_s=int(node.offset.total_seconds()),
                )

        # Create solver model
        model = cp_model.CpModel()

        intervals = []
        makespan = model.NewIntVar(0, max_time, "makespan")

        for node_id, pv in pvars.items():
            _create_protocol_vars(model, pv, node_id, max_time)
            if pv.interval is not None:
                intervals.append(pv.interval)
            if pv.finish_time is not None:
                model.Add(makespan >= pv.finish_time)
        model.AddNoOverlap(intervals)

        # Ordering constraints from domain tree
        for node in nodes:
            if not isinstance(node, protocol.Protocol):
                continue
            pv = pvars[node.id]
            for post_node in node.post_node:
                if isinstance(post_node, protocol.Protocol):
                    post_pv = pvars[post_node.id]
                    if pv.finish_time is not None and post_pv.start_time is not None:
                        model.Add(pv.finish_time <= post_pv.start_time)
                elif isinstance(post_node, protocol.Delay):
                    for delay_post in post_node.post_node:
                        if (
                            isinstance(delay_post, protocol.Protocol)
                            and delay_post.id in pvars
                        ):
                            delay_post_pv = pvars[delay_post.id]
                            if (
                                pv.finish_time is not None
                                and delay_post_pv.start_time is not None
                            ):
                                model.Add(pv.finish_time <= delay_post_pv.start_time)

        # Delay loss constraints
        delay_nodes = [n for n in nodes if isinstance(n, protocol.Delay)]
        losses = [
            _create_delay_loss(model, dn, dvars[dn.id], pvars, max_time)
            for dn in delay_nodes
        ]

        model.minimize(makespan + self.time_loss_weight * sum(losses))
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.max_solve_time
        status = solver.Solve(model)

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE, cp_model.UNKNOWN):
            for node in nodes:
                if isinstance(node, protocol.Protocol) and node.id in pvars:
                    pv = pvars[node.id]
                    if pv.start_time is not None and pv.finish_time is not None:
                        node.scheduled_time = tsc.seconds_to_time(
                            solver.Value(pv.start_time)
                        )
        else:
            status_name = STATUS_STR.get(status, "UNKNOWN")
            raise ValueError(
                f"No optimal schedule found. (status={status_name})"
            )
        return STATUS_STR.get(status, "UNKNOWN")


if __name__ == "__main__":
    s = protocol.Start()
    p1 = protocol.Protocol(name="P1", duration=timedelta(minutes=10))
    p2 = protocol.Protocol(name="P2", duration=timedelta(seconds=3))
    p3 = protocol.Protocol(name="P3", duration=timedelta(seconds=2))

    sec5 = protocol.Delay(
        duration=timedelta(seconds=5), from_type=protocol.FromType.START
    )

    s > p1 > [p2, sec5 > p3]

    p1.started_time = datetime.now()
    p1.finished_time = p1.started_time + timedelta(minutes=10, seconds=1)
    print(s)
    Optimizer(1).optimize_schedule(s)
    print(protocol.format_protocol(s))
