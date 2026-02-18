import unittest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, ANY

# Add 'neuro_agent' to sys.path
sys.path.append(str(Path(__file__).parents[2] / "neuro_agent"))

from langchain_core.messages import HumanMessage
from neuro_agent.src.supervisor.nodes import supervisor_node

class TestSupervisor(unittest.TestCase):
    @patch('neuro_agent.src.supervisor.nodes.boto3.client')
    def test_supervisor_basic_flow(self, mock_boto):
        # Setup Mock Bedrock
        mock_client = mock_boto.return_value
        mock_response = {
            'output': {
                'message': {
                    'role': 'assistant',
                    'content': [{'text': 'Hello user!'}]
                }
            }
        }
        mock_client.converse.return_value = mock_response

        # State
        state = {
            "messages": [HumanMessage(content="Hi")],
            "user_id": "u1",
            "profile": {},
            "todos": []
        }
        
        # Config (Registry Mock)
        mock_registry = MagicMock()
        mock_registry.get_bedrock_config.return_value = [{"toolSpec": {}}]
        config = {"configurable": {"tool_registry": mock_registry}}

        # Run
        result = supervisor_node(state, config)
        
        # Assertions
        self.assertEqual(result['messages'][0].content, 'Hello user!')
        mock_client.converse.assert_called_with(
            modelId="us.amazon.nova-pro-v1:0",
            messages=[{'role': 'user', 'content': [{'text': 'Hi'}]}],
            system=ANY,
            toolConfig={'tools': [{"toolSpec": {}}]}
        )

    @patch('neuro_agent.src.supervisor.nodes.boto3.client')
    def test_supervisor_tool_call(self, mock_boto):
        # Setup Mock Bedrock returning Tool Use
        mock_client = mock_boto.return_value
        mock_response = {
            'output': {
                'message': {
                    'role': 'assistant',
                    'content': [{
                        'toolUse': {
                            'toolUseId': 't1',
                            'name': 'web_search',
                            'input': {'query': 'Find me info'}
                        }
                    }]
                }
            }
        }
        mock_client.converse.return_value = mock_response

        # Registry Mock behavior
        mock_registry = MagicMock()
        mock_runner = MagicMock(return_value="Search Result")
        mock_registry.get_runner.return_value = mock_runner
        config = {"configurable": {"tool_registry": mock_registry}}

        state = {
            "messages": [HumanMessage(content="Search for X")],
            "user_id": "u1"
        }

        # Run
        result = supervisor_node(state, config)

        # Expect Tool Execution Result
        self.assertIn("Action: web_search", result['messages'][0].content)
        self.assertIn("Result: Search Result", result['messages'][0].content)
        mock_runner.assert_called_with(query='Find me info')

if __name__ == '__main__':
    unittest.main()
