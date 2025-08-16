import asyncio
from datetime import datetime, timedelta

from src.awaitlist import AwaitList


async def process_tasks(await_list: AwaitList):
    """Fetch tasks from the list and process them sequentially."""
    async for task in await_list.wait_for_next_task():
        print(f"[Processor] Executing: {task.content} at {datetime.now()}")


async def add_tasks(await_list: AwaitList):
    """Example of dynamically adding tasks."""
    now = datetime.now()
    print(f"[AddTasks] Current time: {now}")

    # Add a task scheduled 5 second later
    task_time_5min = now + timedelta(seconds=5)
    await asyncio.sleep(1)  # Wait 1 second
    await await_list.add_task(task_time_5min, "Task 5 second later")
    print(f"[AddTasks] Added: Task 5 second later for {task_time_5min}")

    await asyncio.sleep(1)  # Wait 1 second

    # Add a task scheduled 1 second later
    task_time_1sec = now + timedelta(seconds=1)
    await await_list.add_task(task_time_1sec, "Task 1 second later")
    print(f"[AddTasks] Added: Task 1 second later for {task_time_1sec}")


async def main():
    await_list = AwaitList()
    await asyncio.gather(process_tasks(await_list), add_tasks(await_list))


# Execute
if __name__ == "__main__":
    asyncio.run(main())
