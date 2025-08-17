import asyncio
from datetime import datetime
from pathlib import Path

import click
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings

from src.awaitlist import AwaitList
from src.schedule import FileScheduleSaver, Scheduler


async def execute_task(task_name: str) -> str:
    print(f"[Task] Executing {task_name} at {datetime.now()}")
    await asyncio.sleep(2)  # Simulate task execution time
    print(f"[Task] Finished {task_name} at {datetime.now()}")
    return f"Executed {task_name} at {datetime.now()}"


async def amain(scheduler_agent: Agent, executor_agent: Agent, scheduler: Scheduler):
    if len(scheduler.await_list.tasks) == 0 and len(scheduler.scheduler_history) == 0:
        result = await scheduler_agent.run("start")
        print(f"[Main] Scheduler initialized: {result.output}")
    await scheduler.process_tasks_with_agent(executor_agent, scheduler_agent)


@click.command()
@click.argument("prompt_file", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--load",
    type=click.Path(),
    default=None,
    help="Load existing scheduler state from file",
)
def main(prompt_file: str, load: str | None):
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
    executor_agent = Agent(
        model,
        model_settings=model_settings,
        system_prompt=("You are a task execution assistant (executor)."),
        tools=[execute_task],
    )
    base_prompt = Path("src/prompt.md").read_text(encoding="utf-8")
    scheduler_prompt = base_prompt.replace("{{experiment_rule}}", prompt_text)
    print(f"[Main] Scheduler prompt: \n{scheduler_prompt}")
    scheduler_agent = Agent(
        "openai:gpt-4o",
        system_prompt=scheduler_prompt,
        tools=[
            scheduler.get_tasks,
            scheduler.add_task,
            scheduler.update_task,
            scheduler.cancel_task,
            scheduler.get_time,
        ],
    )
    asyncio.run(amain(scheduler_agent, executor_agent, scheduler))


if __name__ == "__main__":
    main()
