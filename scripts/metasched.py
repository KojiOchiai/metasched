import asyncio
import logging
from pathlib import Path
from typing import Annotated, Optional
from uuid import UUID

import typer

from src.console import print_protocol_tree, print_schedule
from src.driver import create_driver
from src.executor import (
    Executor,
    IncompleteState,
    InterruptedAction,
    check_incomplete_state,
)
from src.json_storage import LocalJSONStorage
from src.logging_config import setup_logging
from src.optimizer import Optimizer
from src.protocol import Start, load_protocol, protocol_from_dict

setup_logging()
logger = logging.getLogger("main")

app = typer.Typer(help="metasched - constraint-based scheduling optimizer and executor")


def _show_incomplete_state(state: IncompleteState) -> None:
    """Display information about incomplete tasks."""
    typer.echo("Previous incomplete run found.")
    if state.interrupted_names:
        typer.echo(f"  Interrupted tasks: {', '.join(state.interrupted_names)}")
    if state.pending_names:
        typer.echo(f"  Pending tasks: {', '.join(state.pending_names)}")


_ACTION_SHORTCUT = {"r": "retry", "s": "skip", "a": "abort"}


def _prompt_interrupted_action(
    state: IncompleteState,
) -> dict[UUID, InterruptedAction]:
    """Ask the user how to handle each interrupted task.

    Returns a mapping of protocol UUID to the chosen action.
    """
    if not state.interrupted_nodes:
        return {}
    typer.echo("  [r]etry  — restored to pre-task state, re-execute")
    typer.echo("  [s]kip   — restored to post-task state, continue")
    typer.echo("  [a]bort  — sample lost, skip this and all downstream tasks")
    actions: dict[UUID, InterruptedAction] = {}
    for node in state.interrupted_nodes:
        while True:
            choice = typer.prompt(f"  {node.name} [r/s/a]", default="r").strip().lower()
            choice = _ACTION_SHORTCUT.get(choice, choice)
            if choice in ("retry", "skip", "abort"):
                actions[node.id] = InterruptedAction(choice)
                break
            typer.echo("    Invalid choice. Enter r, s, or a.")
    return actions


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
    interrupted: Annotated[
        InterruptedAction,
        typer.Option(help="How to handle interrupted tasks on resume: retry or skip"),
    ] = InterruptedAction.RETRY,
):
    """Execute a schedule with real-time task execution."""
    json_storage = LocalJSONStorage(statefile)
    incomplete = check_incomplete_state(json_storage)

    interrupted_actions: dict[UUID, InterruptedAction] | InterruptedAction = interrupted
    if incomplete is not None:
        _show_incomplete_state(incomplete)
        if not resume and protocolfile is not None:
            resume = typer.confirm("Resume?")
        if resume and incomplete.interrupted_names:
            interrupted_actions = _prompt_interrupted_action(incomplete)

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
        interrupted=interrupted_actions,
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
