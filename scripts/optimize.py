import importlib
import logging
from pathlib import Path
from typing import Annotated, Optional

import typer

from src.console import print_protocol_tree, print_schedule
from src.logging_config import setup_logging
from src.optimizer import Optimizer
from src.protocol import Start

# logging setting
setup_logging()
logger = logging.getLogger("main")


def main(
    protocolfile: Annotated[
        Optional[Path],
        typer.Option(help="Path to the protocol file", exists=True, dir_okay=False),
    ] = None,
    buffer: Annotated[int, typer.Option(help="Buffer time in seconds")] = 0,
):
    if protocolfile is not None:
        protocol_module = importlib.import_module(
            str(protocolfile).replace("/", ".").replace(".py", "")
        )
        # find start object from the module
        protocol: Start | None = next(
            (obj for obj in vars(protocol_module).values() if isinstance(obj, Start)),
            None,
        )
        if protocol is None:
            raise ValueError(
                f"Protocol type 'Start' not found in the module '{protocolfile}'."
            )
        print_protocol_tree(protocol)
    else:
        protocol = None

    logger.info("Optimizing schedule...")
    optimizer = Optimizer(buffer)
    optimizer.optimize_schedule(protocol)
    print_schedule(protocol)


if __name__ == "__main__":
    typer.run(main)
