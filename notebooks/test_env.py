import os
import sys
from dotenv import load_dotenv

project_root = os.path.abspath('..')
if project_root not in sys.path:
    sys.path.insert(0, os.path.join(project_root, 'src'))
    sys.path.insert(0, os.path.join(project_root, 'apps'))
    sys.path.insert(0, project_root)

env_path = os.path.join(project_root, '.env')
print(f"Loading env from {env_path}")
load_dotenv(env_path)
print(f"TAVILY_API_KEY loaded: {'TAVILY_API_KEY' in os.environ}")

# Test the import
from src.neuro_agent.infrastructure.tools.research import tavily_client
print("Tavily client initialized successfully")
