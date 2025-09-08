import importlib
import logging
from datetime import datetime

import click

from src.optimizer import format_schedule, optimize_schedule
from src.protocol import Start

# logging setting
now = datetime.now()
date_str = now.strftime("%Y-%m-%d_%H-%M-%S")
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)


logger = logging.getLogger("main")
logger.setLevel(logging.INFO)


@click.command()
@click.argument("protocol_file", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--protocolname",
    type=str,
    default="start",
    help="Name of the protocol to use",
)
def main(protocol_file: str, protocolname: str):
    protocol_module = importlib.import_module(
        protocol_file.replace("/", ".").replace(".py", "")
    )
    protocol: Start = getattr(protocol_module, protocolname)
    logger.info(protocol)
    logger.info("Optimizing schedule...")
    optimize_schedule(protocol)
    print(format_schedule(protocol))


if __name__ == "__main__":
    main()
