import sys
from pathlib import Path
import os
from dotenv import load_dotenv
load_dotenv()

from apps.supervisor.graph import create_agent_graph
from neuro_agent.domain.config import bootstrap_tool_registry
from neuro_agent.infrastructure.memory.dynamo_checkpointer import ChunkedDynamoDBSaver
from neuro_agent.infrastructure.tools import get_context


def main():
    print("🚀 Starting Local NeuroAgent...")

    # 1. Bootstrap via Factory
    registry = bootstrap_tool_registry()
    print(f"🔧 Tools Loaded: {registry.list_tools()}")

    # 2. Infra
    checkpointer = ChunkedDynamoDBSaver()
    app = create_agent_graph(checkpointer=checkpointer)

    # 3. Injection
    config = {
        "configurable": {
            "thread_id": "local_test_user",
            "tool_registry": registry,
            "fetch_user_context": get_context
        }
    }

    # 4. Interact
    # user_input = input("User: ")
    # Hardcoded for non-interactive run in this environment, but kept the structure
    user_input = "My house is a mess, I need to clean but I am overwhelmed."
    print(f"User: {user_input}")
    
    inputs = {"messages": [("user", user_input)], "user_id": "local_test_user"}
    
    for event in app.stream(inputs, config=config):
        for node, val in event.items():
            if "messages" in val:
                print(f"🤖 {val['messages'][-1].content}")

if __name__ == "__main__":
    main()
