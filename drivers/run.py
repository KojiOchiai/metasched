import asyncio
import logging

import click

from drivers.dummy.driver import execute_task_dummy
from drivers.maholo.driver import execute_task_maholo

logger = logging.getLogger("driver_runner")
logger.setLevel(logging.INFO)


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
    from src.logging.logging_config import setup_logging

    setup_logging()
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)

    main()
