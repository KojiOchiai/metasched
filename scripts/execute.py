import asyncio
import importlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable

import click

from src.awaitlist import AwaitList
from src.driver import execute_task_dummy, execute_task_maholo
from src.executor import Executor, FileExecutorSaver
from src.protocol import Start

# logging setting
log_dir = Path("logs")
log_dir.mkdir(parents=True, exist_ok=True)
now = datetime.now()
date_str = now.strftime("%Y-%m-%d_%H-%M-%S")
logfile_name = log_dir / f"metashed_{date_str}.log"
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(logfile_name, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)


logger = logging.getLogger("main")
logger.setLevel(logging.INFO)


async def amain(driver: Callable[[str], Awaitable], executor: Executor):
    logger.info("[Main] Executor initialized")
    await executor.process_tasks_loop(driver)


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
    protocol_module = importlib.import_module(
        protocol_file.replace("/", ".").replace(".py", "")
    )
    protocol: Start = getattr(protocol_module, protocolname)
    logger.info(protocol)
    if load and Path(load).exists():
        executor_saver = FileExecutorSaver(str(load))
        executor = executor_saver.load()
        executor.protocol = protocol
    else:
        executor_saver = FileExecutorSaver("executor_state")
        await_list = AwaitList()
        executor = Executor(protocol, await_list, saver=executor_saver)
    driver_func = execute_task_maholo if driver == "maholo" else execute_task_dummy
    asyncio.run(amain(driver_func, executor))


if __name__ == "__main__":
    main()
