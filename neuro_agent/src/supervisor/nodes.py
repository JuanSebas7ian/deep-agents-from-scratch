import boto3
import os
import inspect
from pathlib import Path
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from src.shared.state import AgentState

def load_skill() -> str:
    """Loads the supervisor system prompt from the skills directory."""
    # Priority: 
    # 1. ../../../skills/supervisor.md (Relative to this file in src/supervisor)
    # 2. neuro_agent/skills/supervisor.md (Relative to CWD)
    
    candidates = [
        Path(__file__).parents[2] / "skills" / "supervisor.md",
        Path(os.getcwd()) / "neuro_agent" / "skills" / "supervisor.md"
    ]
    
    for path in candidates:
        if path.exists():
            return path.read_text(encoding="utf-8")
            
    return "You are a helpful AI assistant. (Skill file not found)"

def _execute_tool(registry, tool_use: dict, user_id: str) -> str:
    """Executes a tool dynamically, injecting user_id if required."""
    tool_name = tool_use['name']
    runner = registry.get_runner(tool_name)
    
    if not runner:
        return f"Tool '{tool_name}' not found in registry."
    
    try:
        # Dynamic Argument Injection
        # Some infrastructure tools (like Lambda invokers) need context (user_id) 
        # that isn't provided by the LLM's generated arguments.
        sig = inspect.signature(runner)
        kwargs = tool_use['input']
        
        if 'user_id' in sig.parameters and 'user_id' not in kwargs:
            kwargs['user_id'] = user_id
            
        return str(runner(**kwargs))
    except Exception as e:
        return f"Tool Execution Error: {str(e)}"

def supervisor_node(state: AgentState, config: RunnableConfig) -> dict:
    # 1. Dependency Injection
    registry = config.get("configurable", {}).get("tool_registry")
    if not registry: 
        from src.shared.config import bootstrap_tool_registry
        registry = bootstrap_tool_registry()

    # 2. AWS Client Initialization
    client = boto3.client("bedrock-runtime", region_name=os.getenv('AWS_REGION', 'us-east-1'))
    
    # 3. Prompt Assembly (Blackboard Pattern)
    profile_data = str(state.get('profile', {}))
    todos_data = str(state.get('todos', []))
    
    system_blocks = [
        {"text": load_skill()},
        {"text": f"PROFILE: {profile_data}\nTODOS: {todos_data}"},
        {"cachePoint": {"type": "default"}}
    ]
    
    # 4. Message Formatting
    aws_msgs = [
        {"role": "user" if isinstance(m, HumanMessage) else "assistant", "content": [{"text": m.content}]}
        for m in state["messages"]
    ]

    # 5. Inference
    try:
        response = client.converse(
            modelId="us.amazon.nova-pro-v1:0",
            messages=aws_msgs,
            system=system_blocks,
            toolConfig={"tools": registry.get_bedrock_config()}
        )
    except Exception as e:
        return {"messages": [AIMessage(content=f"Error invoking Bedrock: {e}")]}
    
    msg = response['output']['message']
    
    # 6. Tool Dispatch
    # API Reciprocity: Check if the model wants to call a tool
    if 'content' in msg:
        for content_block in msg['content']:
            if 'toolUse' in content_block:
                tool_use = content_block['toolUse']
                
                # Execute Logic Extracted to Helper
                result = _execute_tool(registry, tool_use, state.get("user_id"))
                
                return {"messages": [AIMessage(content=f"Action: {tool_use['name']}\nResult: {result}")]}

    # Default Text Response
    text_content = msg['content'][0]['text'] if 'content' in msg else ""
    return {"messages": [AIMessage(content=text_content)]}
