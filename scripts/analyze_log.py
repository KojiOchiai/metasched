"""Log timeline visualizer for metasched.

Parses structured JSON logs and generates an interactive HTML timeline
using Plotly, showing scheduled vs actual execution times for each protocol.
"""

import json
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import plotly.graph_objects as go
import typer

LOGS_DIR = Path(__file__).parent.parent / "logs"

app = typer.Typer(help="Visualize metasched execution logs as interactive timelines.")


@dataclass
class ProtocolEvent:
    name: str
    scheduled_time: datetime
    started_time: datetime
    finished_time: datetime


@dataclass
class OptimizeEvent:
    timestamp: datetime
    solver_status: str


@dataclass
class SessionInfo:
    log_path: Path
    timestamp: datetime
    protocol_count: int = 0
    duration_seconds: float = 0.0


def _parse_datetime(s: str) -> datetime:
    """Parse ISO format or log asctime format."""
    if "T" in s:
        return datetime.fromisoformat(s)
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S,%f")


def _parse_log(log_path: Path) -> tuple[list[ProtocolEvent], list[OptimizeEvent]]:
    """Parse a log file and extract protocol and optimization events."""
    protocols: list[ProtocolEvent] = []
    optimizations: list[OptimizeEvent] = []

    with open(log_path) as f:
        for line in f:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if entry.get("name") != "executor":
                continue

            func = entry.get("function")
            etype = entry.get("type")

            if func == "optimize" and etype == "end":
                optimizations.append(
                    OptimizeEvent(
                        timestamp=_parse_datetime(entry["asctime"]),
                        solver_status=entry.get("solver_status", ""),
                    )
                )

            if func == "process_task" and "protocol_name" in entry:
                protocols.append(
                    ProtocolEvent(
                        name=entry["protocol_name"],
                        scheduled_time=_parse_datetime(entry["task_execution_time"]),
                        started_time=_parse_datetime(entry["protocol_started_time"]),
                        finished_time=_parse_datetime(entry["protocol_finished_time"]),
                    )
                )

    return protocols, optimizations


def _scan_sessions() -> list[SessionInfo]:
    """Scan logs directory and return session info sorted by newest first."""
    if not LOGS_DIR.exists():
        return []

    sessions: list[SessionInfo] = []
    for log_path in sorted(LOGS_DIR.glob("metasched_*.log"), reverse=True):
        protocols, _ = _parse_log(log_path)
        if not protocols:
            continue

        first = min(p.started_time for p in protocols)
        last = max(p.finished_time for p in protocols)
        ts_str = log_path.stem.replace("metasched_", "")
        try:
            ts = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
        except ValueError:
            ts = first

        sessions.append(
            SessionInfo(
                log_path=log_path,
                timestamp=ts,
                protocol_count=len(protocols),
                duration_seconds=(last - first).total_seconds(),
            )
        )

    return sessions


def _format_duration(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    if m > 0:
        return f"{m}m{s:02d}s"
    return f"{s}s"


def _build_timeline(
    protocols: list[ProtocolEvent], optimizations: list[OptimizeEvent]
) -> go.Figure:
    """Build a Plotly timeline figure."""
    # Sort by started_time for display order
    protocols_sorted = sorted(protocols, key=lambda p: p.started_time)
    names = [p.name for p in protocols_sorted]

    fig = go.Figure()

    # Scheduled time bars (light color, behind actual)
    fig.add_trace(
        go.Bar(
            y=names,
            x=[
                (p.finished_time - p.started_time).total_seconds()
                for p in protocols_sorted
            ],
            base=[
                (p.scheduled_time - protocols_sorted[0].scheduled_time).total_seconds()
                for p in protocols_sorted
            ],
            orientation="h",
            name="Scheduled",
            marker_color="rgba(100, 149, 237, 0.3)",
            hovertemplate=(
                "<b>%{y}</b><br>Scheduled: %{customdata[0]}<br><extra>Scheduled</extra>"
            ),
            customdata=[
                [p.scheduled_time.strftime("%H:%M:%S")] for p in protocols_sorted
            ],
        )
    )

    # Actual execution bars
    t0 = protocols_sorted[0].scheduled_time
    delays = []
    colors = []
    hover_texts = []
    bases = []
    widths = []

    for p in protocols_sorted:
        delay = (p.started_time - p.scheduled_time).total_seconds()
        duration = (p.finished_time - p.started_time).total_seconds()
        delays.append(delay)
        bases.append((p.started_time - t0).total_seconds())
        widths.append(duration)

        if abs(delay) < 1.0:
            colors.append("rgba(76, 175, 80, 0.85)")  # green
        elif abs(delay) < 5.0:
            colors.append("rgba(255, 193, 7, 0.85)")  # yellow
        else:
            colors.append("rgba(244, 67, 54, 0.85)")  # red

        hover_texts.append(
            f"<b>{p.name}</b><br>"
            f"Scheduled: {p.scheduled_time.strftime('%H:%M:%S.%f')[:-3]}<br>"
            f"Started: {p.started_time.strftime('%H:%M:%S.%f')[:-3]}<br>"
            f"Finished: {p.finished_time.strftime('%H:%M:%S.%f')[:-3]}<br>"
            f"Duration: {duration:.1f}s<br>"
            f"Delay: {delay:+.1f}s"
        )

    fig.add_trace(
        go.Bar(
            y=names,
            x=widths,
            base=bases,
            orientation="h",
            name="Actual",
            marker_color=colors,
            hovertemplate="%{customdata}<extra></extra>",
            customdata=hover_texts,
        )
    )

    # Re-optimization markers
    if optimizations:
        opt_times = [(o.timestamp - t0).total_seconds() for o in optimizations]
        opt_labels = [o.solver_status for o in optimizations]
        fig.add_trace(
            go.Scatter(
                x=opt_times,
                y=[names[-1]] * len(opt_times),
                mode="markers",
                name="Re-optimize",
                marker=dict(symbol="diamond", size=8, color="rgba(156, 39, 176, 0.7)"),
                hovertemplate=(
                    "Re-optimize<br>Status: %{customdata}<br><extra></extra>"
                ),
                customdata=opt_labels,
                visible="legendonly",
            )
        )

    # Layout
    session_start = protocols_sorted[0].scheduled_time.strftime("%Y-%m-%d %H:%M:%S")
    total_duration = (
        max(p.finished_time for p in protocols_sorted)
        - min(p.scheduled_time for p in protocols_sorted)
    ).total_seconds()

    fig.update_layout(
        title=dict(
            text=(
                f"Execution Timeline — {session_start}"
                f" — {len(protocols)} protocols"
                f" — {_format_duration(total_duration)}"
            ),
        ),
        xaxis=dict(
            title="Time (seconds from start)",
            showgrid=True,
            gridcolor="rgba(200,200,200,0.3)",
        ),
        yaxis=dict(
            title="",
            autorange="reversed",
            showgrid=False,
        ),
        barmode="overlay",
        height=max(400, len(protocols) * 35 + 100),
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hoverlabel=dict(align="left"),
    )

    return fig


@app.command()
def main(
    log_file: str | None = typer.Argument(None, help="Path to log file"),
    list_sessions: bool = typer.Option(
        False, "--list", "-l", help="List available sessions and select interactively"
    ),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Output HTML path (default: same dir as log)"
    ),
    no_open: bool = typer.Option(False, "--no-open", help="Don't auto-open in browser"),
):
    """Visualize a metasched log as an interactive HTML timeline."""
    log_path: Path | None = None

    if log_file is not None:
        log_path = Path(log_file)
    elif list_sessions:
        sessions = _scan_sessions()
        if not sessions:
            typer.echo("No log sessions with protocol data found.")
            raise typer.Exit(1)

        typer.echo("\nAvailable sessions:\n")
        for i, s in enumerate(sessions, 1):
            typer.echo(
                f"  [{i:2d}] {s.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
                f"  ({s.protocol_count} protocols, {_format_duration(s.duration_seconds)})"
            )
        typer.echo()

        choice = typer.prompt("Select session number", type=int)
        if choice < 1 or choice > len(sessions):
            typer.echo("Invalid selection.")
            raise typer.Exit(1)
        log_path = sessions[choice - 1].log_path
    else:
        # Default: latest session with data
        sessions = _scan_sessions()
        if not sessions:
            typer.echo("No log sessions with protocol data found in logs/")
            raise typer.Exit(1)
        log_path = sessions[0].log_path
        typer.echo(f"Using latest session: {log_path.name}")

    if not log_path.exists():
        typer.echo(f"Log file not found: {log_path}")
        raise typer.Exit(1)

    protocols, optimizations = _parse_log(log_path)
    if not protocols:
        typer.echo(f"No protocol events found in {log_path}")
        raise typer.Exit(1)

    fig = _build_timeline(protocols, optimizations)

    if output is None:
        output = log_path.with_suffix(".html")

    fig.write_html(str(output))
    typer.echo(f"Timeline saved to {output}")

    if not no_open:
        webbrowser.open(f"file://{output.resolve()}")


if __name__ == "__main__":
    app()
