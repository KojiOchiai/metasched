import logging
from pathlib import Path
from typing import Annotated

import typer

from src.console import print_schedule
from src.json_storage import LocalJSONStorage
from src.logging_config import setup_logging
from src.protocol import Start, protocol_from_dict

# logging setting
setup_logging()
logger = logging.getLogger("main")


def main(
    statefile: Annotated[
        Path,
        typer.Option(help="Path to the state file to read"),
    ] = Path(".state.json"),
):
    json_storage = LocalJSONStorage(statefile)
    data = json_storage.load()
    protocols = [protocol_from_dict(d) for d in data["protocols"]]
    starts = [p for p in protocols if type(p) is Start]
    if len(starts) == 0:
        raise ValueError("No Start protocol found in the state file")
    for start in starts:
        print_schedule(start)


if __name__ == "__main__":
    typer.run(main)
