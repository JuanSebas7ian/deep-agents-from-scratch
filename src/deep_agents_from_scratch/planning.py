"""Planning module for Deep Agents.

This module provides functionality to generate static execution plans (SOPs) based on
agent definitions and user queries, before the main agent loop begins.
"""

from typing import List, Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic.v1 import BaseModel, Field

class TodoStep(BaseModel):
    """A single step in the execution plan."""
    task: str = Field(description="Clear, actionable task description")

class TodoPlan(BaseModel):
    """The complete execution plan."""
    steps: List[TodoStep] = Field(description="Ordered list of steps to achieve the objective")

def generate_static_plan(
    model: BaseChatModel, 
    query: str, 
    system_context: str
) -> List[Dict[str, Any]]:
    """
    Generates a static initial plan (SOP) based on the agent's definition and the user's query.
    
    Args:
        model: The LLM to use for planning (e.g., ChatBedrockConverse).
        query: The user's objective or question.
        system_context: The full system prompt of the agent (including tools/skills).
        
    Returns:
        A list of TODO dictionaries: [{"task": "...", "status": "pending"}, ...]
    """
    
    # specialized system prompt for the planner
    planner_system_prompt = (
        "You are an expert Planner for a Deep Agent.\n"
        "Your goal is to create a static Standard Operating Procedure (SOP) "
        "based on the user's request and the agent's capabilities.\n\n"
        "CONTEXT (Agent Definition):\n"
        f"{system_context}\n\n"
        "INSTRUCTIONS:\n"
        "1. Analyze the user's request.\n"
        "2. Review the agent's tools and available skills.\n"
        "3. Create a SIMPLE, HIGH-LEVEL plan (MAXIMUM 3 STEPS) to fulfill the request.\n"
        "4. The plan must be logical and sequential. Avoid granular details.\n"
        "5. Output ONLY the plan as a JSON object with a 'steps' key containing a list of tasks."
    )

    parser = JsonOutputParser(pydantic_object=TodoPlan)
    
    # Create the chain
    chain = (
        ChatPromptTemplate.from_messages([
            ("system", planner_system_prompt),
            ("human", "{query}"),
        ])
        | model
        | parser
    )

    try:
        # Generate the plan
        result = chain.invoke({"query": query})
        
        # Convert to DeepAgents TODO format
        todos = []
        for step in result.get("steps", []):
            task_desc = step if isinstance(step, str) else step.get("task", str(step))
            todos.append({
                "content": task_desc,
                "status": "pending"
            })
            
        return todos

    except Exception as e:
        print(f"⚠️ Failed to generate static plan: {e}")
        # Fallback to an empty plan (agent will have to self-plan)
        return []
