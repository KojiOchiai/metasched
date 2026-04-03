import asyncio
import uuid
from datetime import datetime
from typing import AsyncGenerator

from pydantic import BaseModel


class ATask(BaseModel):
    execution_time: datetime
    id: uuid.UUID
    content: str


class AwaitList:
    """
    Asynchronous task scheduler that waits for the execution time of tasks.
    Provides a mechanism to process tasks sequentially based on time.
    """

    def __init__(self) -> None:
        # Task list [(execution time, task ID, task name)]
        self.tasks: list[ATask] = []
        # For task notification
        self.condition = asyncio.Condition()
        self._done = False

    def to_dict(self) -> dict:
        """
        Convert the AwaitList to a dictionary representation.
        """
        return {"tasks": [task.model_dump(mode="json") for task in self.tasks]}

    @classmethod
    def from_dict(cls, data: dict) -> "AwaitList":
        await_list = cls()
        for task_data in data.get("tasks", []):
            task = ATask.model_validate(task_data)
            await_list.tasks.append(task)
        return await_list

    def get_tasks(self) -> list[ATask]:
        """
        Get the list of all tasks.
        """
        return self.tasks

    async def add_task(
        self, execution_time: datetime, content: str, id: uuid.UUID | None = None
    ) -> ATask:
        """
        Add a new task and return a task ID for cancellation.

        Args:
            execution_time (datetime): Scheduled execution time.
            content (str): Task name.

        Returns:
            ATask: The created task.
        """
        ids = [t.id for t in self.tasks]
        if id in ids:
            raise ValueError(f"Task with id {id} already exists.")
        async with self.condition:
            task_id = id if id is not None else uuid.uuid4()
            task = ATask(execution_time=execution_time, id=task_id, content=content)
            self.tasks.append(task)
            self.tasks.sort(key=lambda x: x.execution_time)  # Sort tasks by time
            self.condition.notify_all()  # Notify waiting processes
            return task

    async def update_task(
        self, task_id: uuid.UUID, execution_time: datetime, content: str
    ) -> bool:
        """
        Update a task in the await list.
        """
        async with self.condition:
            for i, task in enumerate(self.tasks):
                if task.id == task_id:
                    self.tasks[i] = ATask(
                        execution_time=execution_time, id=task_id, content=content
                    )
                    self.condition.notify_all()
                    return True
            return False

    async def mark_done(self) -> None:
        """Signal that no more tasks will be added. The generator will exit."""
        async with self.condition:
            self._done = True
            self.condition.notify_all()

    async def cancel_task(self, task_id: uuid.UUID) -> bool:
        """
        Cancel a task by its ID.

        Args:
            task_id (uuid.UUID): The ID of the task to cancel.

        Returns:
            bool: True if the task was successfully cancelled, False otherwise.
        """
        async with self.condition:
            for i, task in enumerate(self.tasks):
                if task.id == task_id:
                    del self.tasks[i]
                    self.condition.notify_all()
                    return True
            return False

    async def wait_for_next_task(self) -> AsyncGenerator[ATask, None]:
        """
        Wait for the next task and yield it sequentially.

        Yields:
            Task: The next task to be executed.
        """
        active_task = None
        while True:
            if active_task is not None:
                yield active_task  # To avoid locking, yield outside of the condition.
                active_task = None
            async with self.condition:  # Ensure the lock is acquired
                if not self.tasks and self._done:
                    return
                if self.tasks:
                    now = datetime.now()
                    next_task = self.tasks[0]

                    # If the next task is ready to execute
                    if next_task.execution_time <= now:
                        self.tasks.pop(0)  # Remove from the list
                        active_task = next_task
                        continue

                    # Wait until the next task time
                    sleep_time = (next_task.execution_time - now).total_seconds()
                else:
                    # If there are no tasks, wait indefinitely
                    sleep_time = None

            try:
                if sleep_time is not None and sleep_time > 0:
                    # Wait for either a timeout or a new task notification
                    async with self.condition:
                        await asyncio.wait_for(
                            self.condition.wait(), timeout=sleep_time
                        )
                else:
                    # Wait indefinitely for a new task notification
                    async with self.condition:
                        await self.condition.wait()
            except asyncio.TimeoutError:
                pass  # Timeout occurred, recheck the task list
