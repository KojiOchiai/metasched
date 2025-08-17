import logging
import uuid
from datetime import datetime

from pydantic_ai import Agent

from src.awaitlist import AwaitList

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def process_tasks_with_agent(
    await_list: AwaitList, executor: Agent, scheduler: Agent
):
    scheduler_history: list = []
    async for task in await_list.wait_for_next_task():
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
            f"[ProcessTask] Result for running task {task.id}: {result.output}"
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
            message_history=scheduler_history,
        )
        scheduler_history = result.all_messages()
        logger.info(
            f"[ProcessTask] Result for after finishing task {task.id}: {result.output}"
        )


def get_add_task(await_list: AwaitList):
    async def add_task(
        execution_time: datetime, remind_message: str, id: uuid.UUID | None = None
    ):
        """
        Add a new remind_message to the await list.
        """
        task = await await_list.add_task(execution_time, remind_message, id)
        logger.info(
            f"[AddTask] Task added: {task.content} at {task.execution_time} with ID: {task.id}"
        )
        return task

    return add_task


def get_get_tasks(await_list: AwaitList):
    async def get_tasks():
        """
        Get the list of all tasks.
        """
        tasks = await_list.get_tasks()
        logger.info("[GetTasks] Get current tasks")
        return tasks

    return get_tasks


def get_time() -> datetime:
    """
    Get the current time.
    """
    now = datetime.now()
    logger.info(f"[GetTime] Current time: {now}")
    return now
