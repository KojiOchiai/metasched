import asyncio
import json
import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Awaitable, Callable

from src.awaitlist import ATask, AwaitList
from src.optimizer import format_schedule, optimize_schedule
from src.protocol import Delay, FromType, Protocol, Start

formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")


logger = logging.getLogger("executor")
logger.setLevel(logging.INFO)


class Executor:
    def __init__(self, driver: Callable[[str], Awaitable[str]]) -> None:
        self.await_list = AwaitList()
        self.protocols: list[Start] = []
        self.driver: Callable[[str], Awaitable[str]] = driver

    async def add_protocol(self, protocol: Start) -> Start:
        # check duplicate
        ids = [p.id for p in self.protocols]
        if protocol.id in ids:
            raise ValueError("Protocol with the same ID already exists")
        self.protocols.append(protocol)
        await self.optimize()
        return protocol

    async def optimize(self, buffer_seconds: int = 0) -> None:
        logger.info(
            json.dumps(
                {
                    "type": "Optimize",
                    "buffer_seconds": buffer_seconds,
                }
            )
        )
        # optimize all protocol
        marged_protocol = Start()
        for starts in self.protocols:
            marged_protocol > starts.post_node
        optimize_schedule(marged_protocol, buffer_seconds=buffer_seconds)

        # cancel all tasks in await list
        tasks = self.await_list.get_tasks()
        for task in tasks:
            await self.await_list.cancel_task(task.id)

        # get next task
        all_protocol: list[Protocol] = [
            p for p in marged_protocol.flatten() if type(p) is Protocol
        ]
        protocols = [p for p in all_protocol if p.started_time is None]
        next_protocol = min(protocols, key=lambda x: x.scheduled_time or datetime.max)

        # add tasks to await list
        if next_protocol.scheduled_time is None:
            raise ValueError("Next protocol has no scheduled time")
        await self.await_list.add_task(
            execution_time=next_protocol.scheduled_time, content=str(next_protocol.id)
        )

    async def process_task(self, task: ATask):
        logger.info(
            json.dumps(
                {
                    "type": "ProcessTask",
                    "protocol_id": str(task.id),
                    "task_execution_time": task.execution_time.isoformat(),
                }
            )
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
            json.dumps(
                {
                    "type": "ProcessTask",
                    "task_id": str(task.id),
                    "task_content": task.content,
                    "task_execution_time": task.execution_time.isoformat(),
                    "protocol_name": protocol_name,
                    "result": result,
                    "protocol_started_time": current_protocol.started_time.isoformat(),
                    "protocol_finished_time": current_protocol.finished_time.isoformat(),
                }
            )
        )
        await self.optimize()

    async def loop(self) -> None:
        async for task in self.await_list.wait_for_next_task():
            await self.process_task(task)


async def main() -> None:
    from src.driver import execute_task_dummy

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

    executor = Executor(driver=execute_task_dummy)
    await executor.add_protocol(s1)
    await executor.add_protocol(s2)
    print(format_schedule(s1))
    print(format_schedule(s2))


if __name__ == "__main__":
    asyncio.run(main())
