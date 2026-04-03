import asyncio
import logging
from pathlib import Path
from typing import Annotated, Optional

import typer

from src.console import print_protocol_tree, print_schedule
from src.driver import create_driver
from src.executor import Executor
from src.json_storage import LocalJSONStorage
from src.logging_config import setup_logging
from src.optimizer import Optimizer
from src.protocol import Start, load_protocol, protocol_from_dict

setup_logging()
logger = logging.getLogger("main")

app = typer.Typer(help="metasched - constraint-based scheduling optimizer and executor")


@app.command()
def optimize(
    protocolfile: Annotated[
        Optional[Path],
        typer.Option(help="Path to the protocol file", exists=True, dir_okay=False),
    ] = None,
    buffer: Annotated[int, typer.Option(help="Buffer time in seconds")] = 0,
):
    """Optimize a schedule without execution."""
    if protocolfile is not None:
        protocol = load_protocol(protocolfile)
        print_protocol_tree(protocol)
    else:
        protocol = None

    logger.info("Optimizing schedule...")
    optimizer = Optimizer(buffer)
    optimizer.optimize_schedule(protocol)
    print_schedule(protocol)


@app.command()
def execute(
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
    """Execute a schedule with real-time task execution."""
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

    async def aloop():
        if protocol is not None:
            await executor.add_protocol(protocol)
        logger.info({"message": "Executor loop started"})
        await executor.loop()

    asyncio.run(aloop())


@app.command(name="print-schedule")
def print_schedule_cmd(
    statefile: Annotated[
        Path,
        typer.Option(help="Path to the state file to read"),
    ] = Path(".state.json"),
):
    """Read and display existing schedule from stored state file."""
    json_storage = LocalJSONStorage(statefile)
    data = json_storage.load()
    protocols = [protocol_from_dict(d) for d in data["protocols"]]
    starts = [p for p in protocols if type(p) is Start]
    if len(starts) == 0:
        raise ValueError("No Start protocol found in the state file")
    for start in starts:
        print_schedule(start)


if __name__ == "__main__":
    app()
