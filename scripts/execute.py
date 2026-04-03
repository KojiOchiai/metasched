import asyncio
import logging
from pathlib import Path
from typing import Annotated, Optional

import click
import typer

from src.driver import create_driver
from src.executor import Executor, InterruptedAction, check_incomplete_state
from src.json_storage import LocalJSONStorage
from src.logging_config import setup_logging
from src.optimizer import Optimizer
from src.protocol import load_protocol

setup_logging()
logger = logging.getLogger("main")


async def aloop(executor: Executor):
    logger.info({"message": "Executor loop started"})
    await executor.loop()


def _prompt_resume() -> tuple[bool, InterruptedAction]:
    """Ask the user whether to resume and how to handle interrupted tasks."""
    resume = typer.confirm("Previous incomplete run found. Resume?")
    if not resume:
        return False, InterruptedAction.RETRY
    action = typer.prompt(
        "How to handle interrupted tasks?",
        type=click.Choice(["retry", "skip"]),
        default="retry",
    )
    return True, InterruptedAction(action)


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
    interrupted: Annotated[
        InterruptedAction,
        typer.Option(help="How to handle interrupted tasks on resume: retry or skip"),
    ] = InterruptedAction.RETRY,
):
    json_storage = LocalJSONStorage(statefile)

    # If --resume is not explicitly set, check for incomplete previous run
    if not resume and protocolfile is not None:
        if check_incomplete_state(json_storage) is not None:
            resume, interrupted = _prompt_resume()

    if not (protocolfile or resume):
        raise typer.BadParameter("Either --protocolfile or --resume must be specified.")

    if protocolfile is not None and not resume:
        protocol = load_protocol(protocolfile)
        logger.info("Loaded protocol from %s", protocolfile)
    else:
        protocol = None

    executor = Executor(
        optimizer=Optimizer(buffer_seconds=buffer),
        driver=create_driver(driver),
        json_storage=json_storage,
        resume=resume,
        interrupted=interrupted,
    )
    if protocol is not None:
        asyncio.run(executor.add_protocol(protocol))
    asyncio.run(aloop(executor))


if __name__ == "__main__":
    typer.run(main)
