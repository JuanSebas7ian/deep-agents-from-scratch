from typing import Callable, Dict, Any, List, Optional
from dataclasses import dataclass

@dataclass
class ToolDefinition:
    name: str
    description: str
    input_schema: Dict[str, Any]
    runner: Callable[..., Any]

class ToolRegistry:
    """
    Dynamic Tool Manager.
    Decouples the Agent core from specific tool implementations.
    """
    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}

    def register(self, name: str, description: str, schema: Dict[str, Any], runner: Callable):
        """Registers a new capability at runtime."""
        self._tools[name] = ToolDefinition(name, description, schema, runner)

    def get_bedrock_config(self) -> List[Dict[str, Any]]:
        """Adapts registered tools to AWS Bedrock JSON format."""
        return [{
            "toolSpec": {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": {"json": tool.input_schema}
            }
        } for tool in self._tools.values()]

    def get_runner(self, name: str) -> Optional[Callable]:
        """Retrieves the executable function for a tool."""
        tool = self._tools.get(name)
        return tool.runner if tool else None
    
    def list_tools(self) -> List[str]:
        return list(self._tools.keys())
