"""Run the browser agent locally: `uv run python run.py https://example.com`."""

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv
from deepagents import create_deep_agent

from browser_tools import browser_tools

load_dotenv()


async def main(url: str) -> None:
    agent = create_deep_agent(
        model="openai:gpt-6-luna",
        tools=browser_tools,
        system_prompt=(Path(__file__).parent / "instructions.md").read_text(),
    )
    result = await agent.ainvoke({"messages": [{"role": "user", "content": f"Summarize {url}"}]})
    print(result["messages"][-1].text)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python run.py <url>")
    asyncio.run(main(sys.argv[1]))
