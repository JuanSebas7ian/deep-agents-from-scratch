import os
from dotenv import load_dotenv
from src.supervisor.graph import create_agent_graph
from src.shared.config import bootstrap_tool_registry
from src.shared.dynamo_checkpointer import ChunkedDynamoDBSaver
from src.shared.tools import get_context

load_dotenv()

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
