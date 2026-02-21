import boto3
import json
import os
from typing import Annotated, Literal, TypedDict, List, NotRequired, Optional
from botocore.config import Config
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, InjectedState
from langchain_core.messages import SystemMessage, ToolMessage
from langchain_core.tools import tool, InjectedToolCallId, BaseTool
from langgraph.types import Command
from neuro_agent.domain.state import AgentState

def delegate_task(user_id: str, instructions: str) -> str:
    """Envía una tarea compleja al Subagente Ejecutor (Lambda)."""
    config = Config(connect_timeout=2, read_timeout=15, retries={'max_attempts': 0})
    client = boto3.client('lambda', region_name=os.getenv('AWS_REGION', 'us-east-1'), config=config)
    
    arn = os.getenv("EXECUTOR_LAMBDA_ARN")
    if not arn:
        return "Error: EXECUTOR_LAMBDA_ARN no configurado."

    try:
        resp = client.invoke(
            FunctionName=arn,
            InvocationType='RequestResponse',
            Payload=json.dumps({"user_id": user_id, "explicit_instructions": instructions})
        )
        if "FunctionError" in resp:
             return f"Error Subagente: {resp['Payload'].read().decode('utf-8')}"

        payload = json.loads(resp['Payload'].read().decode('utf-8'))
        return payload.get("body", "Tarea delegada exitosamente.")
    except Exception as e:
        return f"Error en delegación: {e}"

class SubAgent(TypedDict):
    name: str
    description: str
    prompt: str
    tools: NotRequired[list[str]]

def create_subagent_tool(tools, subagents: List[SubAgent], llm, state_schema):
    """
    Factory to create a local sub-agent tool wrapping LangGraph workflows.
    Implements context isolation and TODO auto-update.
    """
    from langchain.agents import create_agent # Local import to avoid circular dependencies
    
    agents = {}
    tools_by_name = {t.name if isinstance(t, BaseTool) else tool(t).name: t for t in tools}

    for _agent in subagents:
        _tools = [tools_by_name[t] for t in _agent.get("tools", [])] if "tools" in _agent else tools
        agents[_agent["name"]] = create_agent(
            llm, system_prompt=_agent["prompt"], tools=_tools, state_schema=state_schema
        )

    other_agents_string = "\n".join([f"- {_agent['name']}: {_agent['description']}" for _agent in subagents])
    description_prefix = f"Delegate tasks to specialized agents:\n{other_agents_string}"

    @tool(description=description_prefix)
    def task(
        description: str,
        subagent_type: str,
        state: Annotated[Optional[dict], InjectedState] = None,
        tool_call_id: Annotated[Optional[str], InjectedToolCallId] = None,
    ) -> Command:
        """Delegate a task to a specialized sub-agent with isolated context."""
        if state is None or tool_call_id is None:
            return Command(update={"messages": [ToolMessage("Error: Missing injected arguments", tool_call_id="")]})
        if subagent_type not in agents:
            return f"Error: subagent_type {subagent_type} not found. Allowed: {list(agents.keys())}"

        sub_agent = agents[subagent_type]
        # Context isolation: fresh messages
        sub_state = {**state, "messages": [("user", description)]}
        
        try:
            result = sub_agent.invoke(sub_state)
        except Exception as e:
            return f"Error executing sub-agent: {e}"

        # Auto-update TODOs
        current_todos = state.get("todos", [])
        updated_todos = []
        for t in current_todos:
            if isinstance(t, dict):
                updated_todos.append(t.copy())
            else:
                updated_todos.append({"content": str(t), "status": "pending"})
        
        task_marked = False
        for t in updated_todos:
            if t.get("status") == "pending":
                t["status"] = "completed"
                task_marked = True
                break

        state_update = {
            "files": result.get("files", {}),
            "messages": [
                ToolMessage(
                    content=f"{result['messages'][-1].content}\n\n{'✅ Task automatically marked as completed.' if task_marked else ''}",
                    tool_call_id=tool_call_id
                )
            ]
        }
        if task_marked:
            state_update["todos"] = updated_todos

        return Command(update=state_update)

    return task
