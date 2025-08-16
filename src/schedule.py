import logging
import uuid
from datetime import datetime

from src.awaitlist import AwaitList

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.setLevel(logging.INFO)


async def process_tasks(await_list: AwaitList):
    """Fetch tasks from the list and process them sequentially."""
    async for task in await_list.wait_for_next_task():
        logger.info(f"[Processor] Executing: {task.content} at {datetime.now()}")


def get_add_task(await_list: AwaitList):
    async def add_task(
        execution_time: datetime, content: str, id: uuid.UUID | None = None
    ):
        task = await await_list.add_task(execution_time, content, id)
        logger.info(
            f"[AddTask] Task added: {task.content} at {task.execution_time} with ID: {task.id}"
        )
        return task

    return add_task


def get_time() -> datetime:
    now = datetime.now()
    logger.info(f"[GetTime] Current time: {now}")
    return now
