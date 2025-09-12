import asyncio
import logging

import click

from drivers.maholo.driver import MaholoDriver
from src.settings import maholo_settings

logger = logging.getLogger("driver")
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


driver = MaholoDriver(
    host=maholo_settings.host,
    port=maholo_settings.port,
    base_path=maholo_settings.base_path,
    microscope_image_dir=maholo_settings.microscope_image_dir,
)


async def execute_task_maholo(task_name: str) -> list[str] | None:
    logger.info(
        {"function": "execute_task_maholo", "type": "start", "task_name": task_name}
    )
    result = await driver.run(task_name)
    logger.info(
        {
            "function": "execute_task_maholo",
            "type": "end",
            "task_name": task_name,
            "result": result,
        }
    )
    return result


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
    from src.logging_config import setup_logging

    setup_logging()
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)

    main()
