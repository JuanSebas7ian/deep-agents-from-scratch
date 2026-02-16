from neuro_agent.src.graph import create_agent_graph
from neuro_agent.src.dynamo_client import fetch_context_from_dynamo
from neuro_agent.src.dynamo_checkpointer import DynamoDBSaver

def get_app_runner_agent():
    # 1. Initialize Hot Memory Checkpointer
    memory_saver = DynamoDBSaver(table_name="LangGraphCheckpoints")
    # 2. Build the graph
    return create_agent_graph(checkpointer=memory_saver)

if __name__ == "__main__":
    # Simulate a request in the App Runner context
    app = get_app_runner_agent()
    user_id = "user_neuro_001"
    config = {
        "configurable": {
            "thread_id": user_id,
            "fetch_user_context": fetch_context_from_dynamo
        }
    }
    
    inputs = {
        "messages": [("user", "My house is a mess, I need to clean but I am overwhelmed.")],
        "user_id": user_id
    }
    
    print("App Runner Supervisor is reasoning...")
    result = app.invoke(inputs, config=config)
    print("\n--- AGENT RESPONSE ---")
    print(result["messages"][-1].content)
