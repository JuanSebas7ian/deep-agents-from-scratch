"""Research Tools."""
import os
from datetime import datetime
import uuid, base64
import httpx
import urllib3
import ssl
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_core.tools import InjectedToolArg, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from markdownify import markdownify
from pydantic import BaseModel, Field
from tavily import TavilyClient
from typing import Annotated, Literal, Optional, Any
from langchain_aws import ChatBedrockConverse

# Global SSL Resilience
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except Exception:
    pass

summarization_model = ChatBedrockConverse(model="us.amazon.nova-pro-v1:0", region_name="us-east-1", temperature=0.0)
from deep_agents_from_scratch.prompts import SUMMARIZE_WEB_SEARCH
from neuro_agent.domain.state import AgentState
DeepAgentState = AgentState

tavily_client = TavilyClient()
HTTPX_CLIENT = httpx.Client(timeout=30.0, verify=False)

class Summary(BaseModel):
    filename: str = Field(description="Name of the file to store.")
    summary: str = Field(description="Key learnings from the webpage.")

def get_today_str() -> str:
    return datetime.now().strftime("%a %b %-d, %Y")

def run_tavily_search(search_query: str, max_results: int = 1, topic="general", include_raw_content=True) -> dict:
    try:
        return tavily_client.search(search_query, max_results=max_results, include_raw_content=include_raw_content, topic=topic)
    except Exception as e:
        return {"results": [], "error": f"Tavily search failed: {e}"}

def summarize_webpage_content(webpage_content: str) -> Summary:
    try:
        structured_model = summarization_model.with_structured_output(Summary)
        return structured_model.invoke([HumanMessage(content=SUMMARIZE_WEB_SEARCH.format(webpage_content=webpage_content, date=get_today_str()))])
    except Exception:
        return Summary(filename="search_result.md", summary=webpage_content[:1000])

def process_search_results(results: dict) -> list[dict]:
    processed_results = []
    for result in results.get('results', []):
        url = result['url']
        try:
            response = HTTPX_CLIENT.get(url)
            if response.status_code == 200:
                raw_content = markdownify(response.text)
                summary_obj = summarize_webpage_content(raw_content)
            else:
                raw_content = result.get('raw_content', '')
                summary_obj = Summary(filename="URL_error.md", summary=result.get('content', 'Error reading URL.'))
        except Exception:
            raw_content = result.get('raw_content', '')
            summary_obj = Summary(filename="error.md", summary=result.get('content', 'Connection error.'))
        uid = base64.urlsafe_b64encode(uuid.uuid4().bytes).rstrip(b"=").decode("ascii")[:8]
        name, ext = os.path.splitext(summary_obj.filename)
        summary_obj.filename = f"{name}_{uid}{ext}"
        processed_results.append({'url': url, 'title': result['title'], 'summary': summary_obj.summary, 'filename': summary_obj.filename, 'raw_content': raw_content})
    return processed_results

@tool
def tavily_search(
    query: str, 
    state: Annotated[Optional[dict], InjectedState] = None, 
    tool_call_id: Annotated[Optional[str], InjectedToolCallId] = None, 
    max_results: int = 1, 
    topic: Annotated[Literal["general", "news", "finance"], InjectedToolArg] = "general"
) -> Command:
    """Search web and save results."""
    if state is None or tool_call_id is None:
        return Command(update={"messages": [ToolMessage("Error: Missing injected arguments", tool_call_id="")]})

    res = run_tavily_search(query, max_results=max_results, topic=topic)
    processed = process_search_results(res)
    files = state.get("files", {})
    summaries = []
    for r in processed:
        fn = r['filename']
        files[fn] = f"# {r['title']}\n\n{r['summary']}\n\n{r['raw_content']}"
        summaries.append(f"- {fn}: {r['summary']}...")
    return Command(update={"files": files, "messages": [ToolMessage("🔍 Results:\n" + "\n".join(summaries), tool_call_id=tool_call_id)]})

@tool
def think_tool(reflection: str) -> str:
    """Record a reflection or thought process."""
    return f"Reflection recorded: {reflection}"
