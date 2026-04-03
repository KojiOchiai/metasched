from datetime import datetime, timedelta

from rich.console import Console, Group
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from src.protocol import Delay, Node, Protocol, Start

console = Console()


def _add_node_to_tree(tree: Tree, node: Node) -> None:
    if isinstance(node, Protocol):
        label = f"[bold]{node.name}[/] [dim]({node.duration})[/]"
        branch = tree.add(label)
    elif isinstance(node, Delay):
        label = f"[yellow]Delay[/] [dim]{node.duration} from {node.from_type.name}[/]"
        branch = tree.add(label)
    elif isinstance(node, Start):
        branch = tree
    else:
        branch = tree.add(str(node))
    for child in node.post_node:
        _add_node_to_tree(branch, child)


def print_protocol_tree(start: Start) -> None:
    tree = Tree("[bold cyan]Protocol DAG[/]")
    for child in start.post_node:
        _add_node_to_tree(tree, child)
    console.print(tree)


def print_schedule(start: Start) -> None:
    protocol_nodes: list[Protocol] = [
        node for node in start.flatten() if type(node) is Protocol
    ]
    sorted_nodes = sorted(
        protocol_nodes, key=lambda x: x.scheduled_time or datetime.max
    )

    first_time = sorted_nodes[0].scheduled_time
    last_time = sorted_nodes[-1].scheduled_time
    last_duration = sorted_nodes[-1].duration
    if first_time is None or last_time is None:
        console.print("[red]No scheduled times found.[/]")
        return
    total_duration = last_time - first_time + last_duration

    console.print(f"\n[bold]Schedule[/] [dim](total: {total_duration})[/]")

    table = Table(show_header=True, header_style="bold", padding=(0, 1))
    table.add_column("Name")
    table.add_column("Offset", justify="right")
    table.add_column("Start", justify="center")
    table.add_column("End", justify="center")
    table.add_column("Duration", justify="right")
    table.add_column("Status", justify="center")

    for node in sorted_nodes:
        if node.scheduled_time is None:
            continue
        if node.started_time is not None:
            started = node.started_time
            status = "[yellow]Started[/]"
        else:
            started = node.scheduled_time
            status = ""
        if node.finished_time is not None:
            finished = node.finished_time
            status = "[green]Done[/]"
        else:
            finished = node.scheduled_time + node.duration

        offset = timedelta(seconds=round((started - first_time).total_seconds()))
        duration = timedelta(
            seconds=round((finished - node.scheduled_time).total_seconds())
        )

        table.add_row(
            node.name,
            str(offset),
            started.strftime("%H:%M:%S"),
            finished.strftime("%H:%M:%S"),
            str(duration),
            status,
        )

    console.print(table)

    # Delay section
    delay_nodes: list[Delay] = [
        node for node in start.flatten() if isinstance(node, Delay)
    ]
    if not delay_nodes:
        return

    console.print("\n[bold]Delays[/]")
    dtable = Table(show_header=True, header_style="bold", padding=(0, 1))
    dtable.add_column("From")
    dtable.add_column("To")
    dtable.add_column("Actual", justify="right")
    dtable.add_column("Target", justify="right")

    for delay in delay_nodes:
        pre_node = delay.pre_node
        if pre_node is None:
            continue
        for post_node in delay.post_node:
            if post_node.scheduled_time is None:
                continue
            if pre_node.finished_time is not None:
                pre_finish = pre_node.finished_time
            elif pre_node.scheduled_time is not None:
                pre_finish = pre_node.scheduled_time + pre_node.duration
            else:
                continue
            actual = post_node.scheduled_time - pre_finish
            target = delay.duration + delay.offset
            style = "green" if actual == target else "yellow"
            dtable.add_row(
                pre_node.name,
                post_node.name,
                f"[{style}]{actual}[/]",
                str(target),
            )

    console.print(dtable)


def build_live_display(protocols: list[Start]) -> Group:
    """Build a Rich renderable showing real-time execution status."""
    now = datetime.now()

    # Gather all Protocol nodes
    all_protocols: list[Protocol] = []
    for start in protocols:
        all_protocols.extend(node for node in start.flatten() if type(node) is Protocol)

    if not all_protocols:
        return Group(Text("No protocols scheduled."))

    sorted_nodes = sorted(all_protocols, key=lambda x: x.scheduled_time or datetime.max)

    total = len(sorted_nodes)
    done = sum(1 for n in sorted_nodes if n.finished_time is not None)
    # Time range
    first_time = sorted_nodes[0].scheduled_time or now
    last_node = sorted_nodes[-1]
    if last_node.scheduled_time:
        est_end = last_node.scheduled_time + last_node.duration
        est_total = est_end - first_time
    else:
        est_total = timedelta(0)

    elapsed = now - first_time

    # Header with progress
    elapsed_str = str(timedelta(seconds=max(0, int(elapsed.total_seconds()))))
    total_str = str(timedelta(seconds=int(est_total.total_seconds())))
    header_text = Text.assemble(
        ("Executing", "bold"),
        f"  {done}/{total} done  ",
        (f"{elapsed_str} / {total_str}", "dim"),
    )
    progress_bar = ProgressBar(total=total, completed=done, width=40)

    # Schedule table
    table = Table(show_header=True, header_style="bold", padding=(0, 1))
    table.add_column("Name")
    table.add_column("Offset", justify="right")
    table.add_column("Start", justify="center")
    table.add_column("End", justify="center")
    table.add_column("Duration", justify="right")
    table.add_column("Status", justify="center")

    for node in sorted_nodes:
        if node.scheduled_time is None:
            continue

        # Determine display times and status
        if node.finished_time is not None:
            started = node.started_time or node.scheduled_time
            finished = node.finished_time
            status = "[green]Done[/]"
            row_style = "dim"
        elif node.started_time is not None:
            started = node.started_time
            finished = node.scheduled_time + node.duration
            status = "[bold yellow]Running[/]"
            row_style = ""
        else:
            started = node.scheduled_time
            finished = node.scheduled_time + node.duration
            wait = (node.scheduled_time - now).total_seconds()
            if wait > 0:
                status = f"[dim]in {timedelta(seconds=int(wait))}[/]"
            else:
                status = ""
            row_style = "dim"

        offset = timedelta(seconds=round((started - first_time).total_seconds()))
        if node.started_time is not None and node.finished_time is None:
            # Running: show elapsed time
            duration = timedelta(
                seconds=round((now - node.started_time).total_seconds())
            )
        else:
            duration = timedelta(
                seconds=round((finished - node.scheduled_time).total_seconds())
            )

        table.add_row(
            node.name,
            str(offset),
            started.strftime("%H:%M:%S"),
            finished.strftime("%H:%M:%S"),
            str(duration),
            status,
            style=row_style,
        )

    return Group(header_text, progress_bar, "", table)
