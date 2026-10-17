from managed_deepagents import define_deep_agent

from tools import tracing
from tools.google import connect_google

# Redact secrets from LangSmith traces before upload.
tracing.install()

# Browsing happens in the managed sandbox (see sandbox/), via the built-in `execute` tool.
agent = define_deep_agent(
    name="browser-agent",
    model="openai:gpt-6-luna",
    tools=[connect_google],
)
