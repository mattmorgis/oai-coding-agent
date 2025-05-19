import asyncio
import os

from agents import Agent, RunHooks, Runner, gen_trace_id, trace
from agents.mcp import MCPServerStdio
from dotenv import load_dotenv

load_dotenv()

MOUNT_PATH = os.getenv("MOUNT_PATH")
if not MOUNT_PATH:
    raise RuntimeError("Please set MOUNT_PATH in your .env file")


class LoggingRunHooks(RunHooks):
    """Logs tool invocations as they start and end."""

    async def on_tool_start(self, context, agent, tool):
        print(f"🔧 Invoking tool: {tool.name}", flush=True)

    async def on_tool_end(self, context, agent, tool, result):
        print(
            f"✅ Tool {tool.name} finished. Result:\n{result}\n{'-' * 50}", flush=True
        )


async def main():
    async with MCPServerStdio(
        name="file-system-mcp",
        params={
            "command": "npx",
            "args": [
                "-y",
                "@modelcontextprotocol/server-filesystem",
                MOUNT_PATH,
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
                model_settings=ModelSettings(
                    reasoning={"summary": "auto", "effort": "medium"}
                ),
                mcp_servers=[server],
            )

            previous_response_id = ""
            while True:
                user_input = input("You: ")

                # Check for exit command
                if user_input.lower() in ["exit", "quit", "bye"]:
                    print("\nGoodbye!")
                    break

                print("\n" + "-" * 50)

                result = await Runner.run(
                    agent,
                    user_input,
                    previous_response_id=previous_response_id
                    if previous_response_id
                    else None,
                    max_turns=50,
                    hooks=hooks,
                )
                previous_response_id = result.last_response_id

                print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
