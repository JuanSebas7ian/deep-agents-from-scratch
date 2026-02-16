import json
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import SystemMessage, HumanMessage
# Note: In AWS Lambda, src.dynamo_client must be packaged in the deployment zip
from src.adapters.dynamo_client import write_task_to_dynamo

# The Idiot Agent: Ultra-fast cold start (Nova Lite)
executor_llm = ChatBedrockConverse(
    model_id="us.amazon.nova-lite-v1:0", 
    temperature=0.0
).bind_tools([write_task_to_dynamo])

def lambda_handler(event, context):
    """
    Entry point for AWS Lambda (NeuroAgent-Executor-Subagent-Prod).
    Totally isolated compute environment.
    """
    user_id = event.get("user_id")
    instructions = event.get("explicit_instructions")
    
    system_msg = SystemMessage(
        content=(
            "You are a strict execution agent. "
            f"The current user_id is: {user_id}. "
            "You MUST use your provided tools to execute the exact instructions given."
            "Do not ask questions. Just execute the tools."
        )
    )
    human_msg = HumanMessage(content=instructions)
    
    try:
        response = executor_llm.invoke([system_msg, human_msg])
        return {
            "statusCode": 200,
            "body": str(response.content) if response.content else "Tasks executed successfully by Lambda."
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": f"Lambda subagent execution failed: {e}"
        }
