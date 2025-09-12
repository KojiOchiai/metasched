import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Awaitable, Callable

from src.awaitlist import ATask, AwaitList
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
logger.setLevel(logging.INFO)


class Executor:
    def __init__(
        self,
        optimizer: Optimizer,
        driver: Callable[[str], Awaitable[list[str] | None]],
        json_storage: JSONStorage,
        resume: bool = False,
    ) -> None:
        self.await_list = AwaitList()
        self.protocols: list[Start] = []
        self.optimizer = optimizer
        self.driver: Callable[[str], Awaitable[list[str] | None]] = driver
        self.json_storage = json_storage
        if resume:
            data = self.json_storage.load()
            protocols = [protocol_from_dict(d) for d in data]
            self.protocols = [p for p in protocols if type(p) is Start]
            asyncio.run(self.optimize())

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
        logger.info(
            {
                "function": "add_protocol",
                "type": "end",
                "protocol": {
                    "protocol_id": str(protocol.top.id),
                },
            }
        )
        return protocol

    async def optimize(self, buffer_seconds: int = 0) -> None:
        logger.info(
            {"function": "optimize", "type": "start", "buffer_seconds": buffer_seconds}
        )
        # optimize all protocol
        marged_protocol = Start()
        for start in self.protocols:
            marged_protocol > start.post_node
        solver_status = self.optimizer.optimize_schedule(marged_protocol)
        # reset starts
        for start in self.protocols:
            for node in start.post_node:
                node.pre_node = start

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
            return
        next_protocol = min(protocols, key=lambda x: x.scheduled_time or datetime.max)

        # add tasks to await list
        if next_protocol.scheduled_time is None:
            raise ValueError("Next protocol has no scheduled time")
        await self.await_list.add_task(
            execution_time=next_protocol.scheduled_time, content=str(next_protocol.id)
        )
        filepath = self.json_storage.save([p.to_dict() for p in self.protocols])
        logger.info(
            {
                "function": "optimize",
                "type": "end",
                "solver_status": solver_status,
                "max_solve_time": self.optimizer.max_solve_time,
                "protocols_saved_path": filepath,
                "next_protocol_node": {
                    "protocol_id": str(next_protocol.top.id),
                    "protocol_node_id": str(next_protocol.id),
                    "name": next_protocol.name,
                    "scheduled_time": next_protocol.scheduled_time.isoformat(),
                },
            }
        )

    async def process_task(self, task: ATask):
        logger.info(
            {
                "function": "process_task",
                "type": "start",
                "task": {
                    "id": str(task.id),
                    "execution_time": task.execution_time.isoformat(),
                    "content": task.content,
                },
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
        result = await self.driver(protocol_name)
        current_protocol.finished_time = datetime.now()
        logger.info(
            {
                "function": "process_task",
                "type": "end",
                "task": {
                    "id": str(task.id),
                    "execution_time": task.execution_time.isoformat(),
                    "content": task.content,
                },
                "protocol_node": {
                    "protocol_id": str(current_protocol.top.id),
                    "protocol_node_id": str(current_protocol.id),
                    "name": current_protocol.name,
                    "result": result,
                    "started_time": current_protocol.started_time.isoformat(),
                    "finished_time": current_protocol.finished_time.isoformat(),
                },
            }
        )
        await self.optimize()

    async def loop(self) -> None:
        async for task in self.await_list.wait_for_next_task():
            await self.process_task(task)


async def main() -> None:
    from src.driver import execute_task_dummy
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
        driver=execute_task_dummy,
        json_storage=LocalJSONStorage(),
    )
    await executor.add_protocol(s1)
    await executor.add_protocol(s2)
    print(format_protocol(s1))
    print(format_protocol(s2))


if __name__ == "__main__":
    asyncio.run(main())
