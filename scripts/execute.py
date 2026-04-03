import asyncio
import logging
from pathlib import Path
from typing import Annotated, Optional

import typer

from src.driver import create_driver
from src.executor import Executor
from src.json_storage import LocalJSONStorage
from src.logging_config import setup_logging
from src.optimizer import Optimizer
from src.protocol import load_protocol

setup_logging()
logger = logging.getLogger("main")


async def aloop(executor: Executor):
    logger.info({"message": "Executor loop started"})
    await executor.loop()


def main(
    protocolfile: Annotated[
        Optional[Path],
        typer.Option(help="Path to the protocol file", exists=True, dir_okay=False),
    ] = None,
    buffer: Annotated[int, typer.Option(help="Buffer time in seconds")] = 0,
    resume: Annotated[
        bool, typer.Option(help="Load existing schedule from file")
    ] = False,
    driver: Annotated[
        str, typer.Option(help="Driver to use. maholo/dummy (default: dummy)")
    ] = "dummy",
    statefile: Annotated[
        Path,
        typer.Option(help="Path to the state file for saving/resuming schedules"),
    ] = Path(".state.json"),
):
    # validate options
    if not (protocolfile or resume):
        raise typer.BadParameter("Either --protocolfile or --resume must be specified.")
    if protocolfile and resume:
        raise typer.BadParameter("--protocolfile and --resume cannot be used together.")

    if protocolfile is not None:
        protocol = load_protocol(protocolfile)
        logger.info("Loaded protocol from %s", protocolfile)
    else:
        protocol = None
    executor = Executor(
        optimizer=Optimizer(buffer_seconds=buffer),
        driver=create_driver(driver),
        json_storage=LocalJSONStorage(statefile),
        resume=resume,
    )
    if protocol is not None:
        asyncio.run(executor.add_protocol(protocol))
    asyncio.run(aloop(executor))


if __name__ == "__main__":
    typer.run(main)
