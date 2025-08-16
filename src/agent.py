import asyncio

from pydantic_ai import Agent

from src.awaitlist import AwaitList
from src.schedule import get_add_task, get_time, process_tasks


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
    add_task = get_add_task(await_list)
    await asyncio.gather(run_agent([add_task, get_time]), process_tasks(await_list))


if __name__ == "__main__":
    asyncio.run(main())
