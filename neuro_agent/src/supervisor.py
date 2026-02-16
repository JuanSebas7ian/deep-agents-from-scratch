import os
import boto3
from langchain_core.messages import AIMessage, HumanMessage
from .state import AgentState
from .registry import SUBAGENTS_REGISTRY

bedrock_client = boto3.client("bedrock-runtime", region_name="us-east-1")

def load_skill() -> str:
    # Use path relative to this file
    # This file is in neuro_agent/src/supervisor.py
    # Skills are in neuro_agent/skills/supervisor.md
    current_dir = os.path.dirname(os.path.abspath(__file__)) # neuro_agent/src
    project_base = os.path.dirname(current_dir) # neuro_agent
    path = os.path.join(project_base, "skills", "supervisor.md")
    
    if not os.path.exists(path):
         # Fallback if structure is different
         # Try project root based (assuming cwd is root)
         path = os.path.join(os.getcwd(), "neuro_agent", "skills", "supervisor.md")
    
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

SUPERVISOR_PROMPT = load_skill()

def _format_aws_messages(messages: list) -> list:
    aws_messages = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            aws_messages.append({"role": "user", "content": [{"text": msg.content}]})
        elif isinstance(msg, AIMessage):
            aws_messages.append({"role": "assistant", "content": [{"text": msg.content}]})
    return aws_messages

def _build_dynamic_tools() -> list:
    """Dynamically translates the registry into AWS Bedrock Tool Schemas."""
    aws_tools = []
    for tool_name, config in SUBAGENTS_REGISTRY.items():
        aws_tools.append({
            "toolSpec": {
                "name": tool_name,
                "description": config["description"],
                "inputSchema": {"json": config["schema"]}
            }
        })
    return aws_tools

def supervisor_node(state: AgentState) -> dict:
    """
    Dynamic Master Brain (Nova Pro).
    Reads Blackboard, isolates context, and triggers Lambda functions via registry tools.
    """
    user_id = state.get("user_id")
    profile_data = str(state.get('profile', {}))
    todos_data = str(state.get('todos', []))
    
    # 1. Blackboard Injection + AWS Prompt Caching
    system_blocks = [
        {"text": SUPERVISOR_PROMPT},
        {"text": f"PROFILE RULES: {profile_data}\nCURRENT DB TODOS: {todos_data}"},
        {"cachePoint": {"type": "default"}} 
    ]
    
    aws_messages = _format_aws_messages(state["messages"])
    dynamic_tools = _build_dynamic_tools()
    
    # 2. Brain Execution (Nova Pro)
    # Using Nova Pro as requested, but might fallback to Nova Lite if Pro not available or costly in test
    # Plan says: "Dynamic Master Brain (Nova Pro)" - I stick to plan.
    # Note: user might not have access to Nova Pro. I will use the modelId from plan.
    response = bedrock_client.converse(
        modelId="us.amazon.nova-pro-v1:0", 
        messages=aws_messages,
        system=system_blocks,
        toolConfig={"tools": dynamic_tools}
    )
    
    output_message = response['output']['message']
    
    # 3. Dynamic Tool Execution Dispatcher
    if 'toolUse' in str(output_message):
        # find toolUse block
        tool_use = None
        for content in output_message['content']:
             if 'toolUse' in content:
                 tool_use = content['toolUse']
                 break
        
        if tool_use:
            tool_name = tool_use['name']
            tool_args = tool_use['input']
            
            # Look up the network adapter in the registry
            if tool_name in SUBAGENTS_REGISTRY:
                runner_function = SUBAGENTS_REGISTRY[tool_name]["runner"]
                # Triggers the AWS Lambda synchronously
                tool_result_str = runner_function(user_id=user_id, **tool_args)
            else:
                tool_result_str = f"Error: Tool '{tool_name}' not found."
                
            aws_messages.append({"role": "assistant", "content": [{"toolUse": tool_use}]})
            aws_messages.append({
                "role": "user",
                "content": [{"toolResult": {"toolUseId": tool_use['toolUseId'], "content": [{"text": str(tool_result_str)}]}}]
            })
            
            # 4. Final Empathetic Response (Cache Hit)
            final_response = bedrock_client.converse(
                modelId="us.amazon.nova-pro-v1:0",
                messages=aws_messages,
                system=system_blocks
            )
            final_text = final_response['output']['message']['content'][0]['text']
            return {"messages": [AIMessage(content=final_text)]}

    final_text = output_message['content'][0]['text']
    return {"messages": [AIMessage(content=final_text)]}
