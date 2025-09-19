import asyncio
import logging

logger = logging.getLogger("dummy_driver")
logger.setLevel(logging.INFO)


async def execute_task_dummy(task_name: str) -> list[str] | None:
    logger.info(
        {"function": "execute_task_dummy", "type": "start", "task_name": task_name}
    )
    await asyncio.sleep(2)  # Simulate task execution time
    result = None
    logger.info(
        {
            "function": "execute_task_dummy",
            "type": "end",
            "task_name": task_name,
            "result": result,
        }
    )
    return result
