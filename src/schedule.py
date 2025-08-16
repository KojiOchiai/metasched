import logging
import uuid
from datetime import datetime

from pydantic_ai import Agent

from src.awaitlist import AwaitList

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def process_tasks_with_agent(await_list: AwaitList, agent: Agent):
    async for task in await_list.wait_for_next_task():
        logger.info(
            f"[ProcessTask] Executing task: {task.content} at {task.execution_time}"
        )
        result = await agent.run(task.content + "is finished")
        print(result.output)
        logger.info(f"[ProcessTask] Result for task {task.id}: {result.output}")


def get_add_task(await_list: AwaitList):
    async def add_task(
        execution_time: datetime, content: str, id: uuid.UUID | None = None
    ):
        """
        Add a new task to the await list.
        """
        task = await await_list.add_task(execution_time, content, id)
        logger.info(
            f"[AddTask] Task added: {task.content} at {task.execution_time} with ID: {task.id}"
        )
        return task

    return add_task


def get_time() -> datetime:
    """
    Get the current time.
    """
    now = datetime.now()
    logger.info(f"[GetTime] Current time: {now}")
    return now
