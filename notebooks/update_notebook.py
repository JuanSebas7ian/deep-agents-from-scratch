
import json

nb_path = "/home/juansebas7ian/deep-agents-from-scratch/notebooks/4_full_neuro_agent.ipynb"

try:
    with open(nb_path, "r") as f:
        nb = json.load(f)

    found = False
    for cell in nb["cells"]:
        if cell["cell_type"] == "code":
            source = "".join(cell["source"])
            if "%%writefile ../neuro_agent/src/shared/tools/research.py" in source:
                found = True
                new_source = [
                    "%%writefile ../neuro_agent/src/shared/tools/research.py\n",
                    "\"\"\"Research Tools.\"\"\"\n",
                    "import os\n",
                    "from datetime import datetime\n",
                    "import uuid, base64\n",
                    "import httpx\n",
                    "import urllib3\n",
                    "import ssl\n",
                    "from langchain_core.messages import HumanMessage, ToolMessage\n",
                    "from langchain_core.tools import tool\n",
                    "from langchain_core.tools import InjectedToolArg, InjectedToolCallId\n",
                    "from langgraph.prebuilt import InjectedState\n",
                    "from langgraph.types import Command\n",
                    "from markdownify import markdownify\n",
                    "from pydantic import BaseModel, Field\n",
                    "from tavily import TavilyClient\n",
                    "from typing import Annotated, Literal, Optional, Any\n", 
                    "from langchain_aws import ChatBedrockConverse\n",
                    "\n",
                    "# Global SSL Resilience\n",
                    "urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)\n",
                    "try:\n",
                    "    ssl._create_default_https_context = ssl._create_unverified_context\n",
                    "except Exception:\n",
                    "    pass\n",
                    "\n",
                    "summarization_model = ChatBedrockConverse(model=\"us.amazon.nova-pro-v1:0\", region_name=\"us-east-1\", temperature=0.0)\n",
                    "from deep_agents_from_scratch.prompts import SUMMARIZE_WEB_SEARCH\n",
                    "from neuro_agent.domain.state import AgentState\n",
                    "DeepAgentState = AgentState\n",
                    "\n",
                    "tavily_client = TavilyClient()\n",
                    "HTTPX_CLIENT = httpx.Client(timeout=30.0, verify=False)\n",
                    "\n",
                    "class Summary(BaseModel):\n",
                    "    filename: str = Field(description=\"Name of the file to store.\")\n",
                    "    summary: str = Field(description=\"Key learnings from the webpage.\")\n",
                    "\n",
                    "def get_today_str() -> str:\n",
                    "    return datetime.now().strftime(\"%a %b %-d, %Y\")\n",
                    "\n",
                    "def run_tavily_search(search_query: str, max_results: int = 1, topic=\"general\", include_raw_content=True) -> dict:\n",
                    "    try:\n",
                    "        return tavily_client.search(search_query, max_results=max_results, include_raw_content=include_raw_content, topic=topic)\n",
                    "    except Exception as e:\n",
                    "        return {\"results\": [], \"error\": f\"Tavily search failed: {e}\"}\n",
                    "\n",
                    "def summarize_webpage_content(webpage_content: str) -> Summary:\n",
                    "    try:\n",
                    "        structured_model = summarization_model.with_structured_output(Summary)\n",
                    "        return structured_model.invoke([HumanMessage(content=SUMMARIZE_WEB_SEARCH.format(webpage_content=webpage_content, date=get_today_str()))])\n",
                    "    except Exception:\n",
                    "        return Summary(filename=\"search_result.md\", summary=webpage_content[:1000])\n",
                    "\n",
                    "def process_search_results(results: dict) -> list[dict]:\n",
                    "    processed_results = []\n",
                    "    for result in results.get('results', []):\n",
                    "        url = result['url']\n",
                    "        try:\n",
                    "            response = HTTPX_CLIENT.get(url)\n",
                    "            if response.status_code == 200:\n",
                    "                raw_content = markdownify(response.text)\n",
                    "                summary_obj = summarize_webpage_content(raw_content)\n",
                    "            else:\n",
                    "                raw_content = result.get('raw_content', '')\n",
                    "                summary_obj = Summary(filename=\"URL_error.md\", summary=result.get('content', 'Error reading URL.'))\n",
                    "        except Exception:\n",
                    "            raw_content = result.get('raw_content', '')\n",
                    "            summary_obj = Summary(filename=\"error.md\", summary=result.get('content', 'Connection error.'))\n",
                    "        uid = base64.urlsafe_b64encode(uuid.uuid4().bytes).rstrip(b\"=\").decode(\"ascii\")[:8]\n",
                    "        name, ext = os.path.splitext(summary_obj.filename)\n",
                    "        summary_obj.filename = f\"{name}_{uid}{ext}\"\n",
                    "        processed_results.append({'url': url, 'title': result['title'], 'summary': summary_obj.summary, 'filename': summary_obj.filename, 'raw_content': raw_content})\n",
                    "    return processed_results\n",
                    "\n",
                    "@tool\n",
                    "def tavily_search(\n",
                    "    query: str, \n",
                    "    state: Annotated[Optional[dict], InjectedState] = None, \n",
                    "    tool_call_id: Annotated[Optional[str], InjectedToolCallId] = None, \n",
                    "    max_results: Annotated[int, InjectedToolArg] = 1, \n",
                    "    topic: Annotated[Literal[\"general\", \"news\", \"finance\"], InjectedToolArg] = \"general\"\n",
                    ") -> Command:\n",
                    "    \"\"\"Search web and save results.\"\"\"\n",
                    "    if state is None or tool_call_id is None:\n",
                    "        return Command(update={\"messages\": [ToolMessage(\"Error: Missing injected arguments\", tool_call_id=\"\")]})\n",
                    "\n", 
                    "    res = run_tavily_search(query, max_results=max_results, topic=topic)\n",
                    "    processed = process_search_results(res)\n",
                    "    files = state.get(\"files\", {})\n",
                    "    summaries = []\n",
                    "    for r in processed:\n",
                    "        fn = r['filename']\n",
                    "        files[fn] = f\"# {r['title']}\\n\\n{r['summary']}\\n\\n{r['raw_content']}\"\n",
                    "        summaries.append(f\"- {fn}: {r['summary']}...\")\n",
                    "    return Command(update={\"files\": files, \"messages\": [ToolMessage(\"🔍 Results:\\n\" + \"\\n\".join(summaries), tool_call_id=tool_call_id)]})\n",
                    "\n",
                    "@tool\n",
                    "def think_tool(reflection: str) -> str:\n",
                    "    \"\"\"Record a reflection or thought process.\"\"\"\n",
                    "    return f\"Reflection recorded: {reflection}\"\n"
                ]
                cell["source"] = new_source
                break

    if found:
        with open(nb_path, "w") as f:
            json.dump(nb, f, indent=1)
        print("Notebook updated.")
    else:
        print("Cell not found.")

except Exception as e:
    print(f"Error: {e}")
