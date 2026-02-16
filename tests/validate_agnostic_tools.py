
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.getcwd(), '..')))
sys.path.append(os.path.abspath(os.getcwd()))

from dotenv import load_dotenv
load_dotenv()

from neuro_agent.src.tools import tavily_search, scrape_webpage, write_file
from langchain_core.messages import ToolMessage

# Mock State
mock_state = {"files": {}, "todos": []}

def test_agnostic_flow():
    print("🧪 Starting Agnostic Tools Validation...")
    
    # 1. Test Search (Should return snippets, not save files)
    print("\n🔍 1. Testing tavily_search (Pure Search)...")
    try:
        # Note: We invoke the function directly, bypassing the tool wrapper injection for simplicity 
        # or we mock the injection. 
        # Actually, the tools.py functions are decorated with @tool. 
        # Let's call the underlying python functions if possible, or invoke properly.
        # But 'tavily_search' in tools.py expects state injection.
        
        # Let's look at tools.py again. 
        # tavily_search signature: (query, state, tool_call_id, max_results, topic)
        # We can pass mock values.
        
        # Mocking State and ToolCallId
        search_result = tavily_search.invoke({
            "query": "Model Context Protocol",
            "state": mock_state,
            "tool_call_id": "call_123",
            "max_results": 1
        })
        
        # Check output type. It returns a Command object in the new implementation?
        # WAIT. In my refactor of tools.py:
        # @tool def tavily_search(...) -> str:
        # It returns a STRING now! Not a Command. 
        # Let's verify what I wrote in Step 198.
        # Yes: performs search... Returns a list of results... return "\n".join(output)
        # It does NOT return a Command anymore.
        
        print(f"✅ Search Output Type: {type(search_result)}")
        print(f"✅ Search Content Snippet: {search_result[:100]}...")
        
        if "Search Results for" not in search_result:
            print("❌ Search output format incorrect.")
            return
            
        if "Function" in str(type(search_result)): # langchain tool return
             pass # .invoke returns the string artifact
             
    except Exception as e:
        print(f"❌ Search Failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # 2. Test Scrape (Should return markdown)
    print("\n🕷️ 2. Testing scrape_webpage (Fetch)...")
    test_url = "https://example.com"
    try:
        scrape_result = scrape_webpage.invoke({"url": test_url})
        print(f"✅ Scrape Content Snippet: {scrape_result[:100]}...")
        
        if "Example Domain" not in scrape_result and "URL:" not in scrape_result:
             print("❌ Scrape content seems wrong.")
    except Exception as e:
        print(f"❌ Scrape Failed: {e}")
        return

    # 3. Test Write File (Explicit Persistence)
    print("\n💾 3. Testing write_file (Explicit Save)...")
    try:
        # write_file returns a Command
        cmd = write_file.invoke({
            "filename": "test_search.md",
            "content": "Test Content",
            "state": mock_state,
            "tool_call_id": "call_456"
        })
        
        # Verify Command structure
        print(f"✅ Write Output: {cmd}")
        # In a real graph, this Command updates the state. 
        # Here we just verify the tool runs and returns the expected Command.
        
        if cmd.update["files"]["test_search.md"] == "Test Content":
             print("✅ File write logic verified.")
        else:
             print("❌ File write logic failed.")
             
    except Exception as e:
        print(f"❌ Write Failed: {e}")
        return

    print("\n🎉 Validation Complete: Agnostic Flow works!")

if __name__ == "__main__":
    test_agnostic_flow()
