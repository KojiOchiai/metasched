import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from rich.live import Live

from src.awaitlist import ATask, AwaitList
from src.console import build_live_display, console
from src.driver import Driver
from src.json_storage import JSONStorage
from src.optimizer import Optimizer
from src.protocol import (
    Delay,
    FromType,
    Protocol,
    Start,
    format_protocol,
    protocol_from_dict,
)

logger = logging.getLogger("executor")


class InterruptedAction(str, Enum):
    RETRY = "retry"
    SKIP = "skip"


@dataclass
class IncompleteState:
    """Information about an incomplete previous run."""

    interrupted_names: list[str]
    """Protocol names that were started but not finished."""
    pending_names: list[str]
    """Protocol names that were not yet started."""


def check_incomplete_state(json_storage: JSONStorage) -> IncompleteState | None:
    """Check if the state file has an incomplete run.

    Returns IncompleteState if incomplete, None otherwise.
    """
    try:
        data = json_storage.load()
    except FileNotFoundError:
        return None
    protocols = [protocol_from_dict(d) for d in data["protocols"]]
    all_nodes = sum((p.flatten() for p in protocols), [])
    protocol_nodes = [n for n in all_nodes if isinstance(n, Protocol)]
    interrupted = [
        n.name for n in protocol_nodes
        if n.started_time is not None and n.finished_time is None
    ]
    pending = [
        n.name for n in protocol_nodes
        if n.started_time is None
    ]
    if interrupted or pending:
        return IncompleteState(
            interrupted_names=interrupted,
            pending_names=pending,
        )
    return None


class Executor:
    def __init__(
        self,
        optimizer: Optimizer,
        driver: Driver,
        json_storage: JSONStorage,
        resume: bool = False,
        interrupted: InterruptedAction = InterruptedAction.RETRY,
    ) -> None:
        self.await_list = AwaitList()
        self.protocols: list[Start] = []
        self.optimizer = optimizer
        self.driver = driver
        self.json_storage = json_storage
        if resume:
            data = self.json_storage.load()
            metadata = data.get("metadata", {})
            if metadata:
                self.optimizer.buffer_seconds = metadata.get(
                    "buffer_seconds", self.optimizer.buffer_seconds
                )
                self.optimizer.time_loss_weight = metadata.get(
                    "time_loss_weight", self.optimizer.time_loss_weight
                )
                self.optimizer.max_solve_time = metadata.get(
                    "max_solve_time", self.optimizer.max_solve_time
                )
            protocols = [protocol_from_dict(d) for d in data["protocols"]]
            self.protocols = [p for p in protocols if type(p) is Start]
            self._handle_interrupted_protocols(interrupted)
            asyncio.run(self.optimize())

    def _handle_interrupted_protocols(self, action: InterruptedAction) -> None:
        """Handle protocols that were started but not finished (interrupted)."""
        for start in self.protocols:
            for node in start.flatten():
                if not (
                    isinstance(node, Protocol)
                    and node.started_time is not None
                    and node.finished_time is None
                ):
                    continue
                if action == InterruptedAction.RETRY:
                    logger.warning(
                        {
                            "function": "_handle_interrupted_protocols",
                            "action": "retry",
                            "protocol_id": str(node.id),
                            "protocol_name": node.name,
                            "message": "Resetting interrupted protocol for re-execution",
                        }
                    )
                    node.started_time = None
                else:
                    node.finished_time = node.started_time + node.duration
                    logger.warning(
                        {
                            "function": "_handle_interrupted_protocols",
                            "action": "skip",
                            "protocol_id": str(node.id),
                            "protocol_name": node.name,
                            "message": "Marking interrupted protocol as finished",
                        }
                    )

    def _save_state(self) -> str:
        """Save current protocol state with optimizer metadata."""
        data = {
            "metadata": {
                "buffer_seconds": self.optimizer.buffer_seconds,
                "time_loss_weight": self.optimizer.time_loss_weight,
                "max_solve_time": self.optimizer.max_solve_time,
            },
            "protocols": [p.model_dump(mode="json") for p in self.protocols],
        }
        return self.json_storage.save(data)

    async def add_protocol(self, protocol: Start) -> Start:
        # check duplicate
        if type(protocol) is not Start:
            raise ValueError("Only Start protocol can be added")
        all_exist_nodes: list[Start | Protocol | Delay] = sum(
            [p.flatten() for p in self.protocols], []
        )
        all_exist_ids = [node.id for node in all_exist_nodes]
        ids = [node.id for node in protocol.flatten()]
        all_ids = all_exist_ids + ids
        if len(all_ids) != len(set(all_ids)):
            raise ValueError("Protocol with the same ID already exists")
        self.protocols.append(protocol)
        await self.optimize()
        return protocol

    async def optimize(self, buffer_seconds: int = 0) -> None:
        logger.info(
            {"function": "optimize", "type": "start", "buffer_seconds": buffer_seconds}
        )
        # optimize all protocol
        marged_protocol = Start()
        for starts in self.protocols:
            marged_protocol > starts.post_node
        solver_status = self.optimizer.optimize_schedule(marged_protocol)

        # cancel all tasks in await list
        tasks = self.await_list.get_tasks()
        for task in tasks:
            await self.await_list.cancel_task(task.id)

        # get next task
        all_protocol: list[Protocol] = [
            p for p in marged_protocol.flatten() if type(p) is Protocol
        ]
        protocols = [p for p in all_protocol if p.started_time is None]
        if len(protocols) == 0:
            logger.info({"function": "optimize", "type": "end", "message": "no tasks"})
            self._save_state()
            await self.await_list.mark_done()
            return
        next_protocol = min(protocols, key=lambda x: x.scheduled_time or datetime.max)

        # add tasks to await list
        if next_protocol.scheduled_time is None:
            raise ValueError("Next protocol has no scheduled time")
        await self.await_list.add_task(
            execution_time=next_protocol.scheduled_time, content=str(next_protocol.id)
        )
        filepath = self._save_state()
        logger.info(
            {
                "function": "optimize",
                "type": "end",
                "solver_status": solver_status,
                "max_solve_time": self.optimizer.max_solve_time,
                "protocols_saved_path": filepath,
                "next_protocol_id": str(next_protocol.id),
                "next_protocol_name": next_protocol.name,
                "next_protocol_scheduled_time": next_protocol.scheduled_time.isoformat(),
            }
        )

    async def process_task(self, task: ATask):
        logger.info(
            {
                "function": "process_task",
                "protocol_id": str(task.id),
                "task_execution_time": task.execution_time.isoformat(),
            }
        )
        # get current node
        all_protocols: list[Protocol] = sum([p.flatten() for p in self.protocols], [])
        all_protocols = [node for node in all_protocols if type(node) is Protocol]
        current_nodes = [
            node for node in all_protocols if node.id == uuid.UUID(task.content)
        ]
        if len(current_nodes) == 0:
            raise ValueError(f"No protocol found for task: {task.content}")
        current_protocol = current_nodes[0]

        # execute
        protocol_name: str = current_protocol.name
        current_protocol.started_time = datetime.now()
        self._save_state()
        result = await self.driver.run(protocol_name)
        current_protocol.finished_time = datetime.now()
        logger.info(
            {
                "function": "process_task",
                "task_content": task.content,
                "task_execution_time": task.execution_time.isoformat(),
                "protocol_name": protocol_name,
                "result": result,
                "protocol_started_time": current_protocol.started_time.isoformat(),
                "protocol_finished_time": current_protocol.finished_time.isoformat(),
            }
        )
        await self.optimize()

    def _build_display(self):
        return build_live_display(self.protocols)

    async def loop(self) -> None:
        with Live(
            self._build_display(),
            console=console,
            refresh_per_second=1,
            get_renderable=self._build_display,
        ):
            async for task in self.await_list.wait_for_next_task():
                await self.process_task(task)
        console.print(self._build_display())


async def main() -> None:
    from src.driver import DummyDriver
    from src.json_storage import LocalJSONStorage

    s1 = Start()
    p1 = Protocol(name="P1", duration=timedelta(minutes=10))
    p2 = Protocol(name="P2", duration=timedelta(seconds=3))
    p3 = Protocol(name="P3", duration=timedelta(seconds=2))
    sec4 = Delay(duration=timedelta(seconds=4), from_type=FromType.START)
    sec5 = Delay(duration=timedelta(seconds=5), from_type=FromType.START)
    s1 > p1 > [sec4 > p2, sec5 > p3]

    s2 = Start()
    p1 = Protocol(name="P1", duration=timedelta(minutes=10))
    p2 = Protocol(name="P2", duration=timedelta(seconds=3))
    p3 = Protocol(name="P3", duration=timedelta(seconds=2))
    sec5 = Delay(duration=timedelta(seconds=5), from_type=FromType.START)
    s2 > p1 > [p2, sec5 > p3]

    executor = Executor(
        optimizer=Optimizer(buffer_seconds=10),
        driver=DummyDriver(),
        json_storage=LocalJSONStorage(),
    )
    await executor.add_protocol(s1)
    await executor.add_protocol(s2)
    print(format_protocol(s1))
    print(format_protocol(s2))


if __name__ == "__main__":
    asyncio.run(main())
