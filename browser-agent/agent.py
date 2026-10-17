from managed_deepagents import define_deep_agent

from .tools.browser_tools import browser_tools

agent = define_deep_agent(
    name="browser-agent",
    model="openai:gpt-6-luna",
    tools=browser_tools,
)
