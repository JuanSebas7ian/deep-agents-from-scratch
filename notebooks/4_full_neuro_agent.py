#!/usr/bin/env python
# coding: utf-8

# In[1]:


import sys
import os
from dotenv import load_dotenv
import warnings

# Configurar el Path del Proyecto (para neuro_agent)
project_root = os.path.abspath(os.path.join(os.getcwd(), '..'))
if project_root not in sys.path:
    sys.path.append(project_root)
neuro_agent_dir = os.path.join(project_root, 'neuro_agent')
if neuro_agent_dir not in sys.path:
    sys.path.append(neuro_agent_dir)

# Cargar Variables de Entorno
load_dotenv(os.path.join(project_root, ".env"), override=True)

# Habilitar recarga automática
get_ipython().run_line_magic('load_ext', 'autoreload')
get_ipython().run_line_magic('autoreload', '2')

# Silenciar warnings específicos de LangSmith
warnings.filterwarnings("ignore", message="LangSmith now uses UUID v7")


# In[2]:


import warnings
warnings.filterwarnings(
    "ignore",
    message="LangSmith now uses UUID v7", 
    category=UserWarning,
)


# # Deep Agent for Research
# 
# ## Overview 
# 
# <img src="./assets/agent_header.png" width="800" style="display:block; margin-left:0;">
# 
# Now, we can put everything we have learned together:
# 
# * We will use **TODOs** to keep track of tasks. 
# * We will use **files** to store raw tool call results. 
# * We will **delegate research tasks to sub-agents** for context isolation. 
# 
# ## Search Tool 
# 
# We'll build a search tool that offloads raw contents to files and returns only a summary to the agent. This is a common pattern for long-running agent trajectories, [as we've seen with Manus](https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus)! 
# 
# ### Core Components
# 
# 1. **Search Execution (`run_tavily_search`)**: Performs the actual web search using Tavily API with configurable parameters for results count and topic filtering.
# 
# 2. **Content Summarization (`summarize_webpage_content`)**: Uses a lightweight model (GPT-4o-mini) to generate structured summaries of webpage content, producing both a descriptive filename and key learnings summary.
# 
# 3. **Result Processing (`process_search_results`)**: Fetches full webpage content via HTTP, converts HTML to markdown using `markdownify`, and generates summaries for each result.
# 
# 4. **Context Offloading (`tavily_search` tool)**: The main tool that:
#    - Executes search and processes results
#    - Saves full content to files in agent state (context offloading)
#    - Returns only minimal summaries to the agent (prevents context spam)
#    - Uses LangGraph `Command` to update both files and messages
# 
# 5. **Strategic Thinking (`think_tool`)**: Provides a structured reflection mechanism for agents to analyze findings, assess gaps, and plan next steps in their research workflow.
# 
# This architecture solves the token efficiency problem by storing detailed search results in files while keeping the agent's working context minimal and focused.

# <div style="background-color: #fff3b0; padding: 10px; border-radius: 4px;">
# <b>Note:</b>  
# The <code>create_react_agent</code> was moved from the LangGraph library to the LangChain library and renamed to <code>create_agent</code> in the 1.0 code release post-filming. There are slight changes to the imports and code to accommodate this. The video may display the previous configuration.
# </div>

# In[3]:


get_ipython().run_cell_magic('writefile', '../neuro_agent/infrastructure/tools/research.py', '"""Research Tools."""\nimport os\nfrom datetime import datetime\nimport uuid, base64\nimport httpx\nimport urllib3\nimport ssl\nfrom langchain_core.messages import HumanMessage, ToolMessage\nfrom langchain_core.tools import tool\nfrom langchain_core.tools import InjectedToolArg, InjectedToolCallId\nfrom langgraph.prebuilt import InjectedState\nfrom langgraph.types import Command\nfrom markdownify import markdownify\nfrom pydantic import BaseModel, Field\nfrom tavily import TavilyClient\nfrom typing import Annotated, Literal, Optional, Any\nfrom langchain_aws import ChatBedrockConverse\n\n# Global SSL Resilience\nurllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)\ntry:\n    ssl._create_default_https_context = ssl._create_unverified_context\nexcept Exception:\n    pass\n\nsummarization_model = ChatBedrockConverse(model="us.amazon.nova-pro-v1:0", region_name="us-east-1", temperature=0.0)\nfrom deep_agents_from_scratch.prompts import SUMMARIZE_WEB_SEARCH\nfrom neuro_agent.domain.state import AgentState\nDeepAgentState = AgentState\n\ntavily_client = TavilyClient()\nHTTPX_CLIENT = httpx.Client(timeout=30.0, verify=False)\n\nclass Summary(BaseModel):\n    filename: str = Field(description="Name of the file to store.")\n    summary: str = Field(description="Key learnings from the webpage.")\n\ndef get_today_str() -> str:\n    return datetime.now().strftime("%a %b %-d, %Y")\n\ndef run_tavily_search(search_query: str, max_results: int = 1, topic="general", include_raw_content=True) -> dict:\n    try:\n        return tavily_client.search(search_query, max_results=max_results, include_raw_content=include_raw_content, topic=topic)\n    except Exception as e:\n        return {"results": [], "error": f"Tavily search failed: {e}"}\n\ndef summarize_webpage_content(webpage_content: str) -> Summary:\n    try:\n        structured_model = summarization_model.with_structured_output(Summary)\n        return structured_model.invoke([HumanMessage(content=SUMMARIZE_WEB_SEARCH.format(webpage_content=webpage_content, date=get_today_str()))])\n    except Exception:\n        return Summary(filename="search_result.md", summary=webpage_content[:1000])\n\ndef process_search_results(results: dict) -> list[dict]:\n    processed_results = []\n    for result in results.get(\'results\', []):\n        url = result[\'url\']\n        try:\n            response = HTTPX_CLIENT.get(url)\n            if response.status_code == 200:\n                raw_content = markdownify(response.text)\n                summary_obj = summarize_webpage_content(raw_content)\n            else:\n                raw_content = result.get(\'raw_content\', \'\')\n                summary_obj = Summary(filename="URL_error.md", summary=result.get(\'content\', \'Error reading URL.\'))\n        except Exception:\n            raw_content = result.get(\'raw_content\', \'\')\n            summary_obj = Summary(filename="error.md", summary=result.get(\'content\', \'Connection error.\'))\n        uid = base64.urlsafe_b64encode(uuid.uuid4().bytes).rstrip(b"=").decode("ascii")[:8]\n        name, ext = os.path.splitext(summary_obj.filename)\n        summary_obj.filename = f"{name}_{uid}{ext}"\n        processed_results.append({\'url\': url, \'title\': result[\'title\'], \'summary\': summary_obj.summary, \'filename\': summary_obj.filename, \'raw_content\': raw_content})\n    return processed_results\n\n@tool\ndef tavily_search(\n    query: str, \n    state: Annotated[Optional[dict], InjectedState] = None, \n    tool_call_id: Annotated[Optional[str], InjectedToolCallId] = None, \n    max_results: Annotated[int, InjectedToolArg] = 1, \n    topic: Annotated[Literal["general", "news", "finance"], InjectedToolArg] = "general"\n) -> Command:\n    """Search web and save results."""\n    if state is None or tool_call_id is None:\n        return Command(update={"messages": [ToolMessage("Error: Missing injected arguments", tool_call_id="")]})\n\n    res = run_tavily_search(query, max_results=max_results, topic=topic)\n    processed = process_search_results(res)\n    files = state.get("files", {})\n    summaries = []\n    for r in processed:\n        fn = r[\'filename\']\n        files[fn] = f"# {r[\'title\']}\\n\\n{r[\'summary\']}\\n\\n{r[\'raw_content\']}"\n        summaries.append(f"- {fn}: {r[\'summary\']}...")\n    return Command(update={"files": files, "messages": [ToolMessage("🔍 Results:\\n" + "\\n".join(summaries), tool_call_id=tool_call_id)]})\n\n@tool\ndef think_tool(reflection: str) -> str:\n    """Record a reflection or thought process."""\n    return f"Reflection recorded: {reflection}"\n')


# ## Deep Agent
# 
# Now, we can just apply all of our prior learnings: 
# 
# * We'll give the researcher a `think_tool` and our `search_tool` above.
# * We'll give our parent agent file tools, a `think_tool`, and a `task` tool. 

# In[4]:


from datetime import datetime
from IPython.display import Image, display
from utils import show_prompt, stream_agent

# Imports de neuro_agent
from neuro_agent.domain.state import AgentState
from neuro_agent.infrastructure.tools.research import tavily_search, think_tool, get_today_str
from neuro_agent.infrastructure.tools.delegation import create_subagent_tool
from neuro_agent.infrastructure.tools.filesystem import ls, read_file, write_file
from neuro_agent.infrastructure.tools.planning import write_todos, read_todos

# Import de create_agent (actualizado 1.0)
from langchain.agents import create_agent

# Prompts (importados de deep_agents_from_scratch)
from deep_agents_from_scratch.prompts import (
    FILE_USAGE_INSTRUCTIONS, RESEARCHER_INSTRUCTIONS, SUBAGENT_USAGE_INSTRUCTIONS, TODO_USAGE_INSTRUCTIONS
)

from langchain_aws import ChatBedrockConverse
model = ChatBedrockConverse(model="us.amazon.nova-2-lite-v1:0", region_name="us-east-1", temperature=0.0)

max_concurrent_research_units = 3
max_researcher_iterations = 3

sub_agent_tools = [tavily_search, think_tool]
built_in_tools = [ls, read_file, write_file, write_todos, read_todos, think_tool]

# Configuración del Sub-Agente Researcher
researcher_config = {
    "name": "research-agent",
    "description": "Delegate research to the sub-agent researcher. Only give this researcher one topic at a time.",
    "prompt": RESEARCHER_INSTRUCTIONS.format(date=get_today_str()),
    "tools": ["tavily_search", "think_tool"]
}

# Herramienta de delegación usando el factory de neuro_agent
task_tool = create_subagent_tool(
    tools=sub_agent_tools,
    subagents=[researcher_config],
    llm=model,
    state_schema=AgentState
)

all_tools = list({t.name: t for t in sub_agent_tools + built_in_tools}.values()) + [task_tool]

SUBAGENT_INSTRUCTIONS = SUBAGENT_USAGE_INSTRUCTIONS.format(
    max_concurrent_research_units=max_concurrent_research_units,
    max_researcher_iterations=max_researcher_iterations,
    date=datetime.now().strftime("%a %b %-d, %Y")
)

INSTRUCTIONS = (
    "# TODO MANAGEMENT\n"
    + TODO_USAGE_INSTRUCTIONS
    + "\n\n"
    + "=" * 80
    + "\n\n"
    + "# FILE SYSTEM USAGE\n"
    + FILE_USAGE_INSTRUCTIONS
    + "\n\n"
    + "=" * 80
    + "\n\n"
    + "# SUB-AGENT DELEGATION\n"
    + SUBAGENT_INSTRUCTIONS
)


# In[5]:


show_prompt(RESEARCHER_INSTRUCTIONS)


# In[6]:


from neuro_agent.infrastructure.memory.dynamo_checkpointer import ChunkedDynamoDBSaver
INSTRUCTIONS = (
    "# TODO MANAGEMENT\n"
    + TODO_USAGE_INSTRUCTIONS
    + "\n\n"
    + "=" * 80
    + "\n\n"
    + "# FILE SYSTEM USAGE\n"
    + FILE_USAGE_INSTRUCTIONS
    + "\n\n"
    + "=" * 80
    + "\n\n"
    + "# SUB-AGENT DELEGATION\n"
    + SUBAGENT_INSTRUCTIONS
)

show_prompt(INSTRUCTIONS)


# In[7]:


# Create agent using the unified create_agent factory (1.0 version)
agent = create_agent(
    model, all_tools, system_prompt=INSTRUCTIONS, state_schema=AgentState
)

# Show the agent graphs
display(Image(agent.get_graph(xray=True).draw_mermaid_png()))


# In[8]:


from utils import format_messages

result = agent.invoke(
    {
        "messages": [
            {
                "role": "user",
                "content": "Give me an overview of Model Context Protocol (MCP).",
            }
        ],
    },
    config={"configurable": {"thread_id": "1"}}
)

format_messages(result["messages"])


# Trace: 
# https://smith.langchain.com/public/3a389ec6-8e6e-4f9e-9a82-0d0a9569e6f8/r
# <!-- https://smith.langchain.com/public/1df7a10e-1465-499c-a3e0-86c1d5429324/r -->

# ## Using the Deep Agent Package
# 
# Now you understand the underlying patterns! 
# 
# You can [use the `deepagents` package](
# https://github.com/hwchase17/deepagents) as a simple abstraction:
# 
# * It include the file system tools
# * It includes the todo tool
# * It includes the task tool
# 
# You only need to supply the sub-agent and any tools you want the sub-agent to use.

# In[9]:


from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage

def create_neuro_agent(model, tools, system_prompt, checkpointer):
    workflow = StateGraph(AgentState)
    model_with_tools = model.bind_tools(tools)
    def agent_node(state: AgentState):
        messages = state["messages"]
        if system_prompt:
            messages = [SystemMessage(content=system_prompt)] + messages
        return {"messages": [model_with_tools.invoke(messages)]}
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_edge(START, "agent")
    def should_continue(state: AgentState):
        return "tools" if state["messages"][-1].tool_calls else END
    workflow.add_conditional_edges("agent", should_continue, ["tools", END])
    workflow.add_edge("tools", "agent")
    return workflow.compile(checkpointer=checkpointer)

checkpointer = ChunkedDynamoDBSaver()
agent = create_neuro_agent(model, all_tools, INSTRUCTIONS, checkpointer)
print("✅ NeuroAgent Assembled.")


# In[10]:


result = agent.invoke(
    {
        "messages": [
            {
                "role": "user",
                "content": "Give me an very brief overview of Model Context Protocol (MCP).",
            }
        ],
    },
    config={"configurable": {"thread_id": "1"}}
)

format_messages(result["messages"])


# Trace: 
# https://smith.langchain.com/public/1d626d81-a102-4588-a2fb-cab40a7271f1/r
# <!-- https://smith.langchain.com/public/1ae2d7f6-f901-4ebd-b6c3-6657a55f88ae/r -->

# In[ ]:




