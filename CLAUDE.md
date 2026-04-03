# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

metasched is a constraint-based scheduling optimizer and executor for laboratory automation workflows. It models experiment workflows as DAGs (directed acyclic graphs), optimizes execution order using Google OR-Tools CP-SAT solver, and executes protocols through pluggable hardware drivers (currently: dummy for testing, Maholo for real biolab automation).

## Common Commands

```bash
# Install dependencies
uv sync

# Run optimization only (dry-run)
uv run scripts/optimize.py --protocolfile sample_protocols/protocol_parallel_fast.py --buffer 3

# Execute with dummy driver
uv run scripts/execute.py --protocolfile sample_protocols/protocol_parallel_fast.py --buffer 3 --driver dummy

# Execute with Maholo hardware driver (requires MAHOLO_* env vars)
uv run scripts/execute.py --protocolfile sample_protocols/protocol_parallel.py --buffer 60 --driver maholo

# Resume a previously saved schedule
uv run scripts/execute.py --resume --buffer 3

# View saved schedule
uv run scripts/print_schedule.py

# Lint
uv run ruff check .
uv run ruff format --check .
```

No test suite exists yet.

## Architecture

### Data Flow

1. **Protocol definition** (Python DSL in `sample_protocols/`) → DAG of Start/Protocol/Delay nodes
2. **Optimizer** (`src/optimizer.py`) → assigns `scheduled_time` to each Protocol node via CP-SAT solver
3. **Executor** (`src/executor.py`) → orchestrates async execution, re-optimizes after each completion
4. **Driver** (`src/driver.py`, `drivers/`) → runs individual protocols on hardware or simulated

### Key Abstractions

- **Protocol graph** (`src/protocol.py`): Nodes are `Start`, `Protocol` (work unit with duration), or `Delay` (timing constraint). Chained with `>` operator. `Delay.from_type` controls whether delay is measured from `START` or `FINISH` of the preceding protocol.
- **Optimizer** (`src/optimizer.py`): Converts the DAG into OR-Tools CP model. Minimizes `makespan + time_loss_weight × Σ(delay_loss)`. Delay loss = deviation from target wait time. Re-runs after each protocol completes to adjust remaining schedule.
- **Executor** (`src/executor.py`): Async loop using `AwaitList` (`src/awaitlist.py`) for time-based task scheduling. Persists state via `JSONStorage` (`src/json_storage.py`) to `payloads/` for resumability.
- **Driver** (`src/driver.py`): Abstract base with `run(name)` and `move(name)`. DummyDriver sleeps; MaholoDriver (`drivers/maholo/`) communicates with Bioportal via WebSocket.

### Configuration

`src/settings.py` uses pydantic-settings with `.env` file support. Maholo settings use `MAHOLO_` prefix.

## Conventions

- Language: Python 3.12+, async/await for execution
- Package manager: uv (not pip)
- Linter: ruff
- Build backend: hatchling; packages `src`, `drivers`, `scripts` are installed as top-level packages (imports use `from src.xxx`, `from drivers.xxx`)
- Protocol files in `sample_protocols/` are executable Python that define a `start` variable
- Logs are structured JSON via python-json-logger
