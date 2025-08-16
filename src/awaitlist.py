import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import AsyncGenerator


@dataclass
class ATask:
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
            task_time (datetime): Scheduled execution time.
            task_name (str): Task name.

        Returns:
            uuid.UUID: Task ID that can be used to cancel the task.
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
