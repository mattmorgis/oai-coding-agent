from __future__ import annotations

import asyncio

from agents import Agent, Runner, set_tracing_disabled

set_tracing_disabled(disabled=True)


async def main():
    agent = Agent(
        name="Assistant",
        instructions="You are a helpful assistant that can answer questions and help with tasks.",
        model="o3",
    )

    result = await Runner.run(
        agent,
        "Please fetch the weather for Tokyo, Paris and San Francisco",
    )
    print(result.to_input_list())


if __name__ == "__main__":
    asyncio.run(main())
