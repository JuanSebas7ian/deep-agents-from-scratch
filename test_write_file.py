import sys
sys.path.insert(0, '/home/juansebas7ian/deep-agents-from-scratch/src')
sys.path.insert(0, '/home/juansebas7ian/deep-agents-from-scratch')
from dotenv import load_dotenv
load_dotenv('/home/juansebas7ian/deep-agents-from-scratch/.env')

from neuro_agent.infrastructure.tools import write_file

try:
    print(write_file.invoke({"name": "write_file", "args": {"file_path": "test.txt", "content": "hello"}, "id": "call_123", "type": "tool_call"}))
except Exception as e:
    import traceback
    traceback.print_exc()
