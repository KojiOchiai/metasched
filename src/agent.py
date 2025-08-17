import asyncio
from datetime import datetime

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings

from src.awaitlist import AwaitList
from src.schedule import FileScheduleSaver, Scheduler


async def execute_task(task_name: str) -> str:
    print(f"[Task] Executing {task_name} at {datetime.now()}")
    await asyncio.sleep(2)  # Simulate task execution time
    print(f"[Task] Finished {task_name} at {datetime.now()}")
    return f"Executed {task_name} at {datetime.now()}"


async def main():
    await_list = AwaitList()
    schedule_saver = FileScheduleSaver("scheduler_state")
    scheduler = Scheduler(await_list, saver=schedule_saver)
    model = OpenAIResponsesModel("o3")
    model_settings = OpenAIResponsesModelSettings(
        openai_reasoning_effort="low",
        openai_reasoning_summary="detailed",
    )
    executor = Agent(
        model,
        model_settings=model_settings,
        system_prompt=("You are a task execution assistant (executor)."),
        tools=[execute_task],
    )
    scheduler_agent = Agent(
        "openai:gpt-4o",
        system_prompt=(
            "You are a schedule management assistant (scheduler). \n"
            'Write remind_message like "execute TaskA. note: this is 3rd execution".'
            "Before add new task, check existing tasks by get_tasks to avoid duplication."
            "finished_time is not known until task is finished."
            "As a scheduling task add tasks following rules. \n"
            "- TaskAの終了時刻から15秒後に次のTaskAをスケジュールしてください"
            "- 5回TaskAを実行してください"
            "- 最初のタスクはスタートから2秒後に開始してください"
        ),
        tools=[
            scheduler.get_tasks,
            scheduler.add_task,
            scheduler.update_task,
            scheduler.cancel_task,
            scheduler.get_time,
        ],
    )
    result = await scheduler_agent.run("start")
    print(f"[Main] Scheduler initialized: {result.output}")
    await scheduler.process_tasks_with_agent(executor, scheduler_agent)


if __name__ == "__main__":
    asyncio.run(main())
