import asyncio
from datetime import datetime

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings

from src.awaitlist import AwaitList
from src.schedule import get_add_task, get_get_tasks, get_time, process_tasks_with_agent


async def execute_task(task_name: str) -> str:
    print(f"[Task] Executing {task_name} at {datetime.now()}")
    await asyncio.sleep(2)  # Simulate task execution time
    print(f"[Task] Finished {task_name} at {datetime.now()}")
    return f"Executed {task_name} at {datetime.now()}"


async def main():
    await_list = AwaitList()
    add_task = get_add_task(await_list)
    model = OpenAIResponsesModel("o3")
    model_settings = OpenAIResponsesModelSettings(
        openai_reasoning_effort="low",
        openai_reasoning_summary="detailed",
    )
    executor = Agent(
        model,
        model_settings=model_settings,
        system_prompt=(
            'You are a task execution assistant (executor). \nYou can run "TaskA" or "TaskB"'
        ),
        tools=[execute_task],
    )
    scheduler = Agent(
        "openai:gpt-4o",
        system_prompt=(
            "You are a schedule management assistant (scheduler). \n"
            "Add tasks following rules. \n"
            "- TaskAの終了時刻から15秒後に次のTaskAをスケジュールしてください"
            "- Taskの終了までの時間はその時になるまでわかりません"
            "- 一度入れたスケジュールは削除、修正できないので注意してください。\n"
            "- 5回TaskAを実行してください"
            "- タスク番号はTaskA(3)のように書いて管理してください。\n"
        ),
        tools=[get_get_tasks(await_list), add_task, get_time],
    )
    result = await scheduler.run("initialize schedule")
    print(f"[Main] Scheduler initialized: {result.output}")
    await process_tasks_with_agent(await_list, executor, scheduler)


if __name__ == "__main__":
    asyncio.run(main())
