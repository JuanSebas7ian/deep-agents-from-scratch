import os
import sys
from pathlib import Path

# Add 'neuro_agent' to sys.path to allow 'from src...' imports
sys.path.append(str(Path(__file__).parents[2] / "neuro_agent"))

import unittest
from neuro_agent.src.shared.registry import ToolRegistry
from neuro_agent.src.shared.config import bootstrap_tool_registry
from unittest.mock import patch, MagicMock

# Dummy runner
def dummy_run(x: int) -> int:
    return x + 1

class TestToolRegistry(unittest.TestCase):
    def test_register_and_get(self):
        reg = ToolRegistry()
        reg.register("dummy", "description", {}, dummy_run)
        
        # Test Runner Retrieval
        runner = reg.get_runner("dummy")
        self.assertIsNotNone(runner)
        self.assertEqual(runner(1), 2)
        
        # Test Bedrock Config Generation
        config = reg.get_bedrock_config()
        self.assertEqual(len(config), 1)
        self.assertEqual(config[0]['toolSpec']['name'], "dummy")

    @patch.dict(os.environ, {"ENVIRONMENT": "PRODUCTION"})
    def test_bootstrap_prod(self):
        reg = bootstrap_tool_registry()
        # Should have web_search, web_read, delegate_worker
        tools = reg.list_tools()
        self.assertIn("web_search", tools)
        self.assertIn("delegate_worker", tools)

    @patch.dict(os.environ, {"ENVIRONMENT": "DEV"})
    def test_bootstrap_dev(self):
        reg = bootstrap_tool_registry()
        tools = reg.list_tools()
        self.assertIn("delegate_worker", tools)
        
if __name__ == '__main__':
    unittest.main()
