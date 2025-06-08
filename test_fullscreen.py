#!/usr/bin/env python
"""Test script for the fullscreen console."""

import asyncio
import os
from pathlib import Path

# Set up a dummy API key for testing
os.environ["OPENAI_API_KEY"] = "test-key"

from oai_coding_agent.runtime_config import RuntimeConfig, ModelChoice, ModeChoice
from oai_coding_agent.agent import Agent
from oai_coding_agent.console.fullscreen_console import FullscreenConsole


async def main():
    """Run a test of the fullscreen console."""
    config = RuntimeConfig(
        openai_api_key="test-key",
        github_token=None,
        model=ModelChoice.o4_mini,
        mode=ModeChoice.default,
        repo_path=Path.cwd(),
    )
    
    # Create a mock agent for testing
    agent = Agent(config)
    
    # Create and run the fullscreen console
    console = FullscreenConsole(agent)
    
    print("Starting fullscreen console test...")
    print("Press Ctrl+C twice to exit")
    
    try:
        await console.run()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())