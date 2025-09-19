import importlib
import logging

import click

from src.logging.logging_config import setup_logging
from src.optimizer import Optimizer
from src.protocol import Start, format_protocol

# logging setting
setup_logging()
logger = logging.getLogger("main")
logger.setLevel(logging.INFO)


@click.command()
@click.option(
    "--protocolfile",
    type=click.Path(exists=True, dir_okay=False),
    help="Path to the protocol file",
)
@click.option(
    "--buffer",
    type=int,
    default=0,
    help="Buffer time in seconds",
)
def main(protocolfile: str, buffer: int):
    if protocolfile is not None:
        protocol_module = importlib.import_module(
            protocolfile.replace("/", ".").replace(".py", "")
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
        print(protocol)
    else:
        protocol = None

    logger.info(protocol)
    logger.info("Optimizing schedule...")
    optimizer = Optimizer(buffer)
    optimizer.optimize_schedule(protocol)
    print(format_protocol(protocol))


if __name__ == "__main__":
    main()
