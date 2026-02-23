import sys
sys.path.insert(0, '/home/juansebas7ian/deep-agents-from-scratch/src')
sys.path.insert(0, '/home/juansebas7ian/deep-agents-from-scratch')
from dotenv import load_dotenv
load_dotenv('/home/juansebas7ian/deep-agents-from-scratch/.env')

from neuro_agent.infrastructure.tools.web import tavily_search
from langgraph.prebuilt import ToolNode
from langchain_core.messages import AIMessage

node = ToolNode([tavily_search])
msg = AIMessage(content="", tool_calls=[{"name": "tavily_search", "args": {"query": "model context protocol"}, "id": "call_123", "type": "tool_call"}])
print(node.invoke({"messages": [msg]}))
