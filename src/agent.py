import asyncio
from datetime import datetime, timedelta

from pydantic_ai import Agent

from src.awaitlist import AwaitList
from src.schedule import get_add_task, get_time, process_tasks_with_agent


async def run_agent(tools: list):
    agent = Agent(
        "openai:gpt-4o",
        system_prompt="You are a helpful assistant that can run tasks.",
        tools=tools,
    )
    result = await agent.run("run ExampleTask, after 10 seconds")
    print(f"Agent result: {result.output}")


async def main():
    await_list = AwaitList()
    await await_list.add_task(
        execution_time=datetime.now() + timedelta(seconds=5),
        content="TaskA(1)",
    )
    add_task = get_add_task(await_list)
    agent = Agent(
        "openai:gpt-4o",
        system_prompt=(
            "You are a schedule management assistant. \n"
            "Add tasks following rules. \n"
            "- Add new task named TaskA(n+1) after 15 seconds from TaskA(n) is finished.\n"
            "- Do nothing and just say skip when TaskA(5) is finished."
        ),
        tools=[add_task, get_time],
    )
    await process_tasks_with_agent(await_list, agent)


if __name__ == "__main__":
    asyncio.run(main())
