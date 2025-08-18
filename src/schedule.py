import json
import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter

from src.awaitlist import AwaitList

formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

log_dir = Path("logs")
log_dir.mkdir(parents=True, exist_ok=True)
now = datetime.now()
date_str = now.strftime("%Y-%m-%d_%H-%M-%S")
logfile_name = log_dir / f"schedule_{date_str}.log"
file_handler = logging.FileHandler(logfile_name, encoding="utf-8")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

logger = logging.getLogger("schedule")
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)


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
        content = ModelMessagesTypeAdapter.dump_json(
            scheduler.scheduler_history, indent=2
        )
        (self.directory_path / "scheduler_history.json").write_bytes(content)

    def load(self) -> "Scheduler":
        with open(self.directory_path / "awaitlist.json", "r") as f:
            data = json.load(f)
        await_list = AwaitList.from_dict(data)
        history_bytes = (self.directory_path / "scheduler_history.json").read_bytes()
        scheduler_history = ModelMessagesTypeAdapter.validate_json(history_bytes)
        return Scheduler(await_list, scheduler_history, self)


class Scheduler:
    def __init__(
        self,
        await_list: AwaitList,
        scheduler_history: list[ModelMessage] | None = None,
        saver: ScheduleSaver | None = None,
    ):
        self.await_list = await_list
        self.scheduler_history: list[ModelMessage] = scheduler_history or []
        self.saver = saver or MemoryScheduleSaver()

    async def process_tasks_with_agent(self, executor: Agent, scheduler: Agent):
        async for task in self.await_list.wait_for_next_task():
            logger.info("====================[ProcessTask]====================")
            logger.info(
                f"[ProcessTask] Executing task: {task.content} at {task.execution_time}"
            )
            started_at = datetime.now()
            result = await executor.run(
                f"Start task: id={task.id}, scheduled_at={task.execution_time}, "
                f"contents={task.content}"
            )
            finished_at = datetime.now()
            logger.info(
                f"[ProcessTask] Result for running task {task.id}: {result.output} "
                f"started_at={started_at}, "
                f"finished_at={finished_at}"
            )
            result = await scheduler.run(
                (
                    f"Task finished: id={task.id}, "
                    f"scheduled_at={task.execution_time}, "
                    f"started_at={started_at}, "
                    f"finished_at={finished_at}, "
                    f"contents={task.content}, result={result.output}"
                ),
                message_history=self.scheduler_history,
            )
            self.scheduler_history = result.all_messages()
            logger.info(
                f"[ProcessTask] Result for after finishing task {task.id}: {result.output}"
            )
            self.saver.save(self)

            schedules = json.dumps(
                self.await_list.to_dict(), ensure_ascii=False, indent=2
            )
            print(f"schedules: \n{schedules}")

    async def add_task(
        self, execution_time: datetime, remind_message: str, id: uuid.UUID | None = None
    ):
        """
        Add a new remind_message to the await list.
        """
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
