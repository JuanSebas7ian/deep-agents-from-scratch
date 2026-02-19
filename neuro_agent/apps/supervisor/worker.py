import os
import boto3
import json
import time
from dotenv import load_dotenv
from apps.supervisor.graph import create_agent_graph
from domain.config import bootstrap_tool_registry
from infrastructure.memory.dynamo_checkpointer import ChunkedDynamoDBSaver
from infrastructure.tools import get_context

load_dotenv()

def process_message(body: str):
    """Runs the Graph for one message."""
    data = json.loads(body)
    user_id = data.get("user_id")
    
    # 1. Load Factory & Infra
    registry = bootstrap_tool_registry()
    checkpointer = ChunkedDynamoDBSaver()
    app = create_agent_graph(checkpointer=checkpointer)
    
    # 2. Inject Dependencies
    config = {
        "configurable": {
            "thread_id": user_id,
            "tool_registry": registry, # <--- INJECTED HERE
            "fetch_user_context": get_context
        }
    }
    
    # 3. Run
    inputs = {"messages": [("user", data.get("message"))], "user_id": user_id}
    print(f"🧠 Thinking for {user_id}...")
    
    for event in app.stream(inputs, config=config):
        pass # Process stream
    print("✅ Done.")
    return True

def main():
    sqs = boto3.client("sqs", region_name=os.getenv("AWS_REGION"))
    queue_url = os.getenv("SQS_QUEUE_URL")
    print(f"🚀 Worker listening on {queue_url}")
    
    while True:
        try:
            if not queue_url:
                print("SQS_QUEUE_URL not set. Worker idle.")
                time.sleep(10)
                continue

            resp = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=1, WaitTimeSeconds=20)
            if "Messages" in resp:
                for msg in resp["Messages"]:
                    if process_message(msg["Body"]):
                        sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=msg["ReceiptHandle"])
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
