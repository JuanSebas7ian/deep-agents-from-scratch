import sys
import os
sys.path.append(os.path.abspath(os.path.join("src")))

from langchain_aws import ChatBedrockConverse
from deep_agents_from_scratch.planning import generate_static_plan

# Mock model or real one? Real one is fine for a quick test.
model = ChatBedrockConverse(model="us.amazon.nova-2-lite-v1:0", region_name="us-east-1")
query = "Research the MCP protocol and summarize its security features."
context = "You are a research agent with tools: tavily_search, read_file, write_file."

print("Generating plan...")
plan = generate_static_plan(model, query, context)
print("\nPlan generated:")
for step in plan:
    print(f"- {step['content']}")
