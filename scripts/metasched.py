import asyncio
import importlib
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
from src.protocol import Start, format_protocol, protocol_from_dict

# logging setting
setup_logging()
logger = logging.getLogger("main")

app = typer.Typer(help="metasched - constraint-based scheduling optimizer and executor")


def load_protocol(protocolfile: Path) -> Start:
    """Load a protocol from a Python file and return the Start object."""
    protocol_module = importlib.import_module(
        str(protocolfile).replace("/", ".").replace(".py", "")
    )
    protocol: Start | None = next(
        (obj for obj in vars(protocol_module).values() if isinstance(obj, Start)),
        None,
    )
    if protocol is None:
        raise ValueError(
            f"Protocol type 'Start' not found in the module '{protocolfile}'."
        )
    return protocol


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
    payloaddir: Annotated[
        Path,
        typer.Option(
            help="Directory to store payloads. If not set, payloads will be stored in the ./payloads directory"
        ),
    ] = Path("payloads"),
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
        json_storage=LocalJSONStorage(str(payloaddir)),
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
    payloaddir: Annotated[
        Path,
        typer.Option(
            help="Directory to store payloads. If not set, payloads will be searched in the ./payloads directory"
        ),
    ] = Path("payloads"),
):
    """Read and display existing schedule from stored payloads."""
    json_storage = LocalJSONStorage(str(payloaddir))
    data = json_storage.load()
    protocols = [protocol_from_dict(d) for d in data]
    starts = [p for p in protocols if type(p) is Start]
    if len(starts) == 0:
        raise ValueError("No Start protocol found in the payloads")
    for protocol in starts:
        print(format_protocol(protocol))


if __name__ == "__main__":
    app()
