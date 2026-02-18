import os
import uuid
import base64
import httpx
from datetime import datetime
from typing import List, Literal, Annotated, Dict, Any, Optional

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool, InjectedToolArg, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from pydantic import BaseModel, Field
from tavily import TavilyClient

from langchain_aws import ChatBedrockConverse
from neuro_agent.src.shared.state import AgentState

try:
    from markdownify import markdownify
except ImportError:
    markdownify = None

# Initialize clients (Lazy initialization might be better but for now global is fine as per notebook pattern)
# We assume the environment is set up correctly (AWS credentials etc.)
# Note: region_name might need to be configurable.
try:
    # Use a default model for summarization, can be overridden if needed
    summarization_model = ChatBedrockConverse(model="us.amazon.nova-pro-v1:0", region_name="us-east-1", temperature=0.0)
except Exception as e:
    print(f"Warning: Could not initialize Bedrock model: {e}")
    summarization_model = None

try:
    tavily_client = TavilyClient()
except Exception:
    tavily_client = None

# --- Prompts ---
SUMMARIZE_WEB_SEARCH = """
You are a research assistant. Summarize the following webpage content.
Date: {date}
Content:
{webpage_content}
"""

class Summary(BaseModel):
    """Schema for webpage content summarization."""
    filename: str = Field(description="Name of the file to store.")
    summary: str = Field(description="Key learnings from the webpage.")

def get_today_str() -> str:
    """Get current date in a human-readable format."""
    return datetime.now().strftime("%a %b %-d, %Y")

def run_tavily_search(
    search_query: str, 
    max_results: int = 1, 
    topic: Literal["general", "news", "finance"] = "general", 
    include_raw_content: bool = True, 
) -> dict:
    """Perform search using Tavily API for a single query."""
    if not tavily_client:
        return {"results": [], "error": "Tavily client not initialized"}
        
    result = tavily_client.search(
        search_query,
        max_results=max_results,
        include_raw_content=include_raw_content,
        topic=topic
    )
    return result

def summarize_webpage_content(webpage_content: str) -> Summary:
    """Summarize webpage content using the configured summarization model."""
    if not summarization_model:
         return Summary(
            filename="search_result.md",
            summary=webpage_content[:500] + "..."
        )

    try:
        structured_model = summarization_model.with_structured_output(Summary)
        summary_and_filename = structured_model.invoke([
            HumanMessage(content=SUMMARIZE_WEB_SEARCH.format(
                webpage_content=webpage_content[:15000], 
                date=get_today_str()
            ))
        ])
        return summary_and_filename
    except Exception:
        return Summary(
            filename="search_result.md",
            summary=webpage_content[:1000] + "..." if len(webpage_content) > 1000 else webpage_content
        )


def process_search_results(results: dict) -> List[dict]:
    """Process search results by summarizing content where available."""
    processed_results = []
    # Use a new client for each process or shared? Shared is better for connection pooling but simple is fine.
    # The notebook creates a new Client.
    with httpx.Client(timeout=30.0) as client:
        for result in results.get('results', []):
            url = result['url']
            try:
                if not result.get('raw_content'):
                    response = client.get(url)
                    if response.status_code == 200:
                        if markdownify:
                            raw_content = markdownify(response.text)
                        else:
                            raw_content = response.text
                    else:
                        raw_content = result.get('content', '')
                else:
                     raw_content = result.get('raw_content', '')
                
                summary_obj = summarize_webpage_content(raw_content)

            except (httpx.TimeoutException, httpx.RequestError, Exception):
                raw_content = result.get('content', '')
                summary_obj = Summary(
                    filename="error.md",
                    summary="Error processing content."
                )

            uid = base64.urlsafe_b64encode(uuid.uuid4().bytes).rstrip(b"=").decode("ascii")[:8]
            name, ext = os.path.splitext(summary_obj.filename)
            if not ext: ext = ".md"
            summary_obj.filename = f"{name}_{uid}{ext}"

            processed_results.append({
                'url': result['url'],
                'title': result['title'],
                'summary': summary_obj.summary,
                'filename': summary_obj.filename,
                'raw_content': raw_content,
            })

    return processed_results


@tool
def tavily_search(
    query: str,
    state: Annotated[AgentState, InjectedState], 
    tool_call_id: Annotated[str, InjectedToolCallId],
    max_results: Annotated[int, InjectedToolArg] = 1,
    topic: Annotated[Literal["general", "news", "finance"], InjectedToolArg] = "general",
) -> Command:
    """Search web and save detailed results to files while returning minimal context."""
    search_results = run_tavily_search(
        query,
        max_results=max_results,
        topic=topic,
        include_raw_content=True,
    ) 

    processed_results = process_search_results(search_results)
    
    files = state.get("files", {})
    if files is None: files = {}
    
    saved_files = []
    summaries = []
    
    for i, result in enumerate(processed_results):
        filename = result['filename']
        
        file_content = f"""# Search Result: {result['title']}

**URL:** {result['url']}
**Query:** {query}
**Date:** {get_today_str()}

## Summary
{result['summary']}

## Raw Content
{result['raw_content'] if result['raw_content'] else 'No raw content available'}
"""
        
        files[filename] = file_content
        saved_files.append(filename)
        summaries.append(f"- {filename}: {result['summary']}...")
    
    summary_text = f"""🔍 Found {len(processed_results)} result(s) for '{query}':

{chr(10).join(summaries)}

Files: {', '.join(saved_files)}
💡 Use read_file() to access full details when needed."""

    return Command(
        update={
            "files": files,
            "messages": [
                ToolMessage(summary_text, tool_call_id=tool_call_id)
            ],
        }
    )

@tool
def scrape_webpage(url: str) -> str:
    """
    Scrape the content of a webpage and return it as markdown.
    """
    try:
        if markdownify:
            # We can use the same logic as process_search_results but for a single URL
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url)
                response.raise_for_status()
                return markdownify(response.text)
        else:
            return "Markdownify not available, cannot scrape."
    except Exception as e:
        return f"Error scraping webpage {url}: {e}"

@tool
def read_page(url: str) -> str:
    """Alias for scrape_webpage."""
    return scrape_webpage(url)
