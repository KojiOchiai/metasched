import asyncio
import importlib
import logging

import click

from src.driver import execute_task_dummy, execute_task_maholo
from src.executor import Executor
from src.json_storage import LocalJSONStorage
from src.logging_config import setup_logging
from src.protocol import Start

# logging setting
setup_logging()
logger = logging.getLogger("main")
logger.setLevel(logging.INFO)


async def aloop(executor: Executor):
    logger.info({"message": "Executor loop started"})
    await executor.loop()


@click.command()
@click.option(
    "--protocolfile",
    type=click.Path(exists=True, dir_okay=False),
    help="Path to the protocol file",
)
@click.option(
    "--resume",
    is_flag=True,
    help="Load existing schedule from file",
)
@click.option(
    "--driver",
    type=str,
    default="dummy",
    help="Driver to use. maholo/dummy (default: dummy)",
)
@click.option(
    "--payloaddir",
    type=click.Path(),
    default="payloads",
    help="Directory to store payloads. If not set, payloads will be stored in the ./payloads directory",
)
def main(
    protocolfile: str,
    resume: bool,
    driver: str,
    payloaddir: str,
):
    # validate options
    if not (protocolfile or resume):
        raise click.UsageError("Either --protocolfile or --resume must be specified.")
    if protocolfile and resume:
        raise click.UsageError("--protocolfile and --resume cannot be used together.")

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

    print(resume)
    driver_func = execute_task_maholo if driver == "maholo" else execute_task_dummy
    executor = Executor(
        driver=driver_func, json_storage=LocalJSONStorage(payloaddir), resume=resume
    )
    if protocol is not None:
        asyncio.run(executor.add_protocol(protocol))
    asyncio.run(aloop(executor))


if __name__ == "__main__":
    main()
