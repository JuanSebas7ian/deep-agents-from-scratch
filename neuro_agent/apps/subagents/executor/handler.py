from langchain_aws import ChatBedrockConverse
from langchain_core.messages import SystemMessage, HumanMessage
import json
# Imported from shared lib inside the zip
from infrastructure.tools import save_task

# Warm start initialization
llm = ChatBedrockConverse(model_id="us.amazon.nova-lite-v1:0").bind_tools([save_task])

def lambda_handler(event, context):
    """Stateless Executor Handler."""
    user_id = event.get("user_id")
    instructions = event.get("explicit_instructions")
    
    try:
        resp = llm.invoke([
            SystemMessage(content=f"Strict Executor for user: {user_id}."),
            HumanMessage(content=instructions)
        ])
        return {"statusCode": 200, "body": str(resp.content)}
    except Exception as e:
        return {"statusCode": 500, "body": str(e)}
