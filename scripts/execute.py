import asyncio
import importlib
import logging

import click

from src.driver import execute_task_dummy, execute_task_maholo
from src.executor import Executor
from src.logging_config import setup_logging
from src.protocol import Start

# logging setting
setup_logging()
logger = logging.getLogger("main")
logger.setLevel(logging.INFO)


async def aloop(executor: Executor):
    logger.info({"message": "Executor initialized"})
    await executor.loop()


async def amain(protocol_file: str, protocolname: str, load: str | None, driver: str):
    protocol_module = importlib.import_module(
        protocol_file.replace("/", ".").replace(".py", "")
    )
    protocol: Start = getattr(protocol_module, protocolname)
    print(protocol)
    driver_func = execute_task_maholo if driver == "maholo" else execute_task_dummy
    executor = Executor(driver=driver_func)
    await executor.add_protocol(protocol)
    await aloop(executor)


@click.command()
@click.argument("protocol_file", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--protocolname",
    type=str,
    default="start",
    help="Name of the protocol to use",
)
@click.option(
    "--load",
    type=click.Path(),
    default=None,
    help="Load existing executor state from file",
)
@click.option(
    "--driver",
    type=str,
    default="dummy",
    help="Driver to use. maholo/dummy (default: dummy)",
)
def main(protocol_file: str, protocolname: str, load: str | None, driver: str):
    asyncio.run(amain(protocol_file, protocolname, load, driver))


if __name__ == "__main__":
    main()
