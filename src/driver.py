import asyncio
import logging
from datetime import datetime

import click

from maholocon.driver import MaholoDriver
from src.settings import maholo_settings

logger = logging.getLogger("driver")
logger.setLevel(logging.INFO)


async def execute_task_dummy(task_name: str) -> str:
    logger.info(f"[Dummy] Executing {task_name} at {datetime.now()}")
    await asyncio.sleep(2)  # Simulate task execution time
    logger.info(f"[Dummy] Finished {task_name} at {datetime.now()}")
    return f"Executed {task_name} at {datetime.now()}"


driver = MaholoDriver(
    host=maholo_settings.host,
    port=maholo_settings.port,
    base_path=maholo_settings.base_path,
    microscope_image_dir=maholo_settings.microscope_image_dir,
)


async def execute_task_maholo(task_name: str) -> str:
    logger.info(f"[Maholo Protocol] Executing {task_name} at {datetime.now()}")
    result = await driver.run(task_name)
    logger.info(
        f"[Maholo Protocol] Finished {task_name} at {datetime.now()} result: {result}"
    )
    return f"Executed {task_name} at {datetime.now()}"


@click.command()
@click.argument("task_name", type=str)
@click.option(
    "--driver",
    type=str,
    default="dummy",
    help="Driver to use. maholo/dummy (default: dummy)",
)
def main(task_name: str, driver: str = "dummy") -> None:
    if driver == "dummy":
        asyncio.run(execute_task_dummy(task_name))
    else:
        asyncio.run(execute_task_maholo(task_name))


if __name__ == "__main__":
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    main()
