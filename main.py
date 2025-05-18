import asyncio

from agents import Agent, Runner, gen_trace_id, trace
from agents.mcp import MCPServerStdio
from dotenv import load_dotenv

load_dotenv()


async def main():
    async with MCPServerStdio(
        name="file-system-mcp",
        params={
            "command": "npx",
            "args": [
                "-y",
                "@modelcontextprotocol/server-filesystem",
                "/Users/matt/Developer/",
            ],
        },
        cache_tools_list=True,
    ) as server:
        trace_id = gen_trace_id()
        with trace(workflow_name="OAI Coding Agent", trace_id=trace_id):
            agent = Agent(
                name="Coding Agent",
                instructions="You are a helpful agent that can answer questions and help with tasks. Use the tools to navigate and read the codebase, and answer questions based on those files. When exploring repositories, avoid using directory_tree on the root directory. Instead, use list_directory to explore one level at a time and search_files to find relevant files matching patterns. If you need to understand a specific subdirectory structure, use directory_tree only on that targeted directory.",
                model="codex-mini-latest",
                mcp_servers=[server],
            )

            history = []
            while True:
                user_input = input("You: ")

                # Check for exit command
                if user_input.lower() in ["exit", "quit", "bye"]:
                    print("\nGoodbye!")
                    break

                print("\n" + "-" * 50)

                result = await Runner.run(
                    agent,
                    history + [{"role": "user", "content": user_input}],
                    max_turns=50,
                )
                history = result.to_input_list()

                print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
