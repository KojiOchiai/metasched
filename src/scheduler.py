import json
import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Awaitable, Callable

from src.awaitlist import ATask, AwaitList
from src.protocol import Delay, FromType, Protocol, Start

formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")


logger = logging.getLogger("schedule")
logger.setLevel(logging.INFO)


class ScheduleSaver(ABC):
    @abstractmethod
    def save(self, scheduler: "Scheduler") -> None:
        raise NotImplementedError()

    @abstractmethod
    def load(self) -> "Scheduler":
        raise NotImplementedError()


class MemoryScheduleSaver(ScheduleSaver):
    def __init__(self) -> None:
        self._scheduler_state: "Scheduler" | None = None

    def save(self, scheduler: "Scheduler") -> None:
        self._scheduler_state = scheduler

    def load(self) -> "Scheduler":
        if self._scheduler_state is None:
            raise ValueError("No scheduler state saved.")
        return self._scheduler_state


class FileScheduleSaver(ScheduleSaver):
    def __init__(self, directory_path: str = "scheduler_state") -> None:
        self.directory_path = Path(directory_path)
        self.directory_path.mkdir(parents=True, exist_ok=True)

    def save(self, scheduler: "Scheduler") -> None:
        with open(self.directory_path / "awaitlist.json", "w") as f:
            json.dump(scheduler.await_list.to_dict(), f, ensure_ascii=False, indent=2)
        with open(self.directory_path / "schedule.json", "w") as f:
            json.dump(scheduler.protocol.to_dict(), f, ensure_ascii=False, indent=2)

    def load(self) -> "Scheduler":
        with open(self.directory_path / "awaitlist.json", "r") as f:
            data = json.load(f)
        await_list = AwaitList.from_dict(data)
        with open(self.directory_path / "schedule.json", "r") as f:
            data = json.load(f)
        protocol = Start.from_dict(data)
        return Scheduler(protocol, await_list=await_list, saver=self)


class Scheduler:
    def __init__(
        self,
        protocol: Start,
        await_list: AwaitList | None = None,
        saver: ScheduleSaver | None = None,
    ):
        self.protocol = protocol
        self.await_list = await_list or AwaitList()
        self.saver = saver or MemoryScheduleSaver()

    async def new_schedules(
        self,
        current_node: Start | Protocol | Delay,
        started_at: datetime,
        finished_at: datetime,
    ):
        # new schedules
        for node in current_node.post_node:
            if isinstance(node, Delay):
                if node.from_type == FromType.START:
                    scheduled_at = self.add_time(
                        started_at, node.duration + node.offset
                    )
                if node.from_type == FromType.FINISH:
                    scheduled_at = self.add_time(
                        finished_at, node.duration + node.offset
                    )
                new_protocol: Protocol = node.post_node[0]
                if new_protocol.name is None:
                    raise ValueError("Protocol name cannot be None")
                await self.add_task(scheduled_at, new_protocol.name)
            elif isinstance(node, Protocol):
                if node.name is None:
                    raise ValueError("Protocol name cannot be None")
                await self.add_task(datetime.now(), node.name)
        self.saver.save(self)
        schedules = json.dumps(self.await_list.to_dict(), ensure_ascii=False, indent=2)
        logger.info(f"schedules: \n{schedules}")

    async def process_task(
        self, executor: Callable[[str], Awaitable[str]], task: ATask
    ):
        logger.info("====================[ProcessTask]====================")
        logger.info(
            f"[ProcessTask] Executing task: {task.content} at {task.execution_time}"
        )
        # get current node
        current_nodes = [
            node
            for node in self.protocol.flatten()
            if isinstance(node, Protocol) and (node.name == task.content)
        ]
        if len(current_nodes) == 0:
            raise ValueError(f"No protocol found for task: {task.content}")
        current_node = current_nodes[0]

        # execute
        protocol_name: str = current_node.name  # type: ignore
        started_at = datetime.now()
        result = await executor(protocol_name)
        finished_at = datetime.now()
        logger.info(
            f"[ProcessTask] Result for running task {task.id}: {task.content} "
            f"result: {result}, "
            f"started_at={started_at}, "
            f"finished_at={finished_at}"
        )
        await self.new_schedules(current_node, started_at, finished_at)

    async def process_tasks_loop(self, executor: Callable[[str], Awaitable[str]]):
        if len(self.await_list.tasks) == 0:
            await self.new_schedules(self.protocol, datetime.now(), datetime.now())  # type: ignore
        async for task in self.await_list.wait_for_next_task():
            await self.process_task(executor, task)

    async def add_task(
        self, execution_time: datetime, remind_message: str, id: uuid.UUID | None = None
    ):
        """
        Add a new remind_message to the await list.
        """
        execution_time = execution_time.replace(tzinfo=None)  # Ensure timezone-naive
        task = await self.await_list.add_task(execution_time, remind_message, id)
        logger.info(
            f"[AddTask] Task added: {task.content} at {task.execution_time} with ID: {task.id}"
        )
        self.saver.save(self)
        return task

    async def update_task(
        self, task_id: uuid.UUID, execution_time: datetime, remind_message: str
    ) -> bool:
        """
        Update a task in the await list.
        """
        execution_time = execution_time.replace(tzinfo=None)  # Ensure timezone-naive
        result = await self.await_list.update_task(
            task_id, execution_time, remind_message
        )
        logger.info(f"[UpdateTask] Result for updating task {task_id}: {result}")
        self.saver.save(self)
        return result

    async def cancel_task(self, task_id: uuid.UUID) -> bool:
        """
        Cancel a task in the await list.
        """
        result = await self.await_list.cancel_task(task_id)
        logger.info(f"[CancelTask] Result for cancelling task {task_id}: {result}")
        self.saver.save(self)
        return result

    async def get_tasks(self):
        """
        Get the list of all tasks.
        """
        tasks = self.await_list.get_tasks()
        logger.info("[GetTasks] Get current tasks")
        self.saver.save(self)
        return tasks

    def get_time(self) -> datetime:
        """
        Get the current time.
        """
        now = datetime.now()
        logger.info(f"[GetTime] Current time: {now}")
        self.saver.save(self)
        return now

    def add_time(self, start: datetime, duration: timedelta) -> datetime:
        """
        Add a duration to a start time.
        """
        # set timezone
        start = start.replace(tzinfo=None)
        end = start + duration
        logger.info(f"[AddTime] Added {duration} to {start}, new time is {end}")
        return end
