import logging
from pathlib import Path
from typing import Annotated

import typer

from src.json_storage import LocalJSONStorage
from src.logging_config import setup_logging
from src.protocol import Start, format_protocol, protocol_from_dict

# logging setting
setup_logging()
logger = logging.getLogger("main")


def main(
    payloaddir: Annotated[
        Path,
        typer.Option(
            help="Directory to store payloads. If not set, payloads will be searched in the ./payloads directory"
        ),
    ] = Path("payloads"),
):
    json_storage = LocalJSONStorage(payloaddir)
    data = json_storage.load()
    protocols = [protocol_from_dict(d) for d in data]
    starts = [p for p in protocols if type(p) is Start]
    if len(starts) == 0:
        raise ValueError("No Start protocol found in the payloads")
    for protocol in starts:
        print(format_protocol(protocol))


if __name__ == "__main__":
    typer.run(main)
