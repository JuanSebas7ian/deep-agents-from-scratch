from .web import tavily_search, scrape_webpage, read_page
from .database import save_task, get_context
from .delegation import delegate_task

# Esto define qué funciones son "Las Tools Oficiales"
__all__ = [
    "tavily_search", 
    "scrape_webpage",
    "read_page", 
    "save_task", 
    "get_context", 
    "delegate_task"
]
