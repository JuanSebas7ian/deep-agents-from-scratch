from datetime import datetime
from langchain_core.tools import tool

def get_today_str() -> str:
    """Get the current date as a string."""
    return datetime.now().strftime("%Y-%m-%d")
