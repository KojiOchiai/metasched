import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

import click
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings

from maholocon.driver import MaholoDriver
from src.awaitlist import AwaitList
from src.schedule import FileScheduleSaver, Scheduler
from src.settings import settings

# logging setting
log_dir = Path("logs")
log_dir.mkdir(parents=True, exist_ok=True)
now = datetime.now()
date_str = now.strftime("%Y-%m-%d_%H-%M-%S")
logfile_name = log_dir / f"metashed_{date_str}.log"
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(logfile_name, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)


logger = logging.getLogger("main")
logger.setLevel(logging.INFO)


async def execute_task_dummy(task_name: str) -> str:
    logger.info(f"[Task] Executing {task_name} at {datetime.now()}")
    await asyncio.sleep(2)  # Simulate task execution time
    logger.info(f"[Task] Finished {task_name} at {datetime.now()}")
    return f"Executed {task_name} at {datetime.now()}"


driver = MaholoDriver(
    host=settings.host,
    port=settings.port,
    base_path=settings.base_path,
    microscope_image_dir=settings.microscope_image_dir,
)


async def execute_task_maholo(task_name: str) -> str:
    logger.info(f"[Maholo Protocol] Executing {task_name} at {datetime.now()}")
    result = await driver.run(task_name)
    logger.info(
        f"[Maholo Protocol] Finished {task_name} at {datetime.now()} result: {result}"
    )
    return f"Executed {task_name} at {datetime.now()}"


async def amain(scheduler_agent: Agent, executor_agent: Agent, scheduler: Scheduler):
    if len(scheduler.await_list.tasks) == 0 and len(scheduler.scheduler_history) == 0:
        result = await scheduler_agent.run("start")
        logger.info(f"[Main] Scheduler initialized: {result.output}")
        schedules = json.dumps(
            scheduler.await_list.to_dict(), ensure_ascii=False, indent=2
        )
        logger.info(f"schedules: \n{schedules}")
    await scheduler.process_tasks_with_agent(executor_agent, scheduler_agent)


@click.command()
@click.argument("prompt_file", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--load",
    type=click.Path(),
    default=None,
    help="Load existing scheduler state from file",
)
@click.option(
    "--driver",
    type=str,
    default="dummy",
    help="Driver to use. maholo/dummy (default: dummy)",
)
def main(prompt_file: str, load: str | None, driver: str):
    prompt_text = Path(prompt_file).read_text(encoding="utf-8")
    if load and Path(load).exists():
        schedule_saver = FileScheduleSaver(str(load))
        scheduler = schedule_saver.load()
    else:
        schedule_saver = FileScheduleSaver("scheduler_state")
        await_list = AwaitList()
        scheduler = Scheduler(await_list, saver=schedule_saver)
    model = OpenAIResponsesModel("o3")
    model_settings = OpenAIResponsesModelSettings(
        openai_reasoning_effort="low",
        openai_reasoning_summary="detailed",
    )
    execute_task = execute_task_maholo if driver == "maholo" else execute_task_dummy
    executor_agent = Agent(
        model,
        model_settings=model_settings,
        system_prompt=("You are a task execution assistant (executor)."),
        tools=[execute_task],
    )
    base_prompt = Path("src/prompt.md").read_text(encoding="utf-8")
    scheduler_prompt = base_prompt.replace("{{experiment_rule}}", prompt_text)
    logger.info(f"[Main] Scheduler prompt: \n{scheduler_prompt}")
    scheduler_agent = Agent(
        "openai:gpt-4o",
        system_prompt=scheduler_prompt,
        tools=[
            scheduler.get_tasks,
            scheduler.add_task,
            scheduler.update_task,
            scheduler.cancel_task,
            scheduler.add_time,
        ],
    )
    asyncio.run(amain(scheduler_agent, executor_agent, scheduler))


if __name__ == "__main__":
    main()
