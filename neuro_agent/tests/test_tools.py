import unittest
from unittest.mock import patch, MagicMock
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parents[2]))

from infrastructure.tools import web, database, delegation

class TestWebTools(unittest.TestCase):
    @patch('neuro_agent.infrastructure.tools.web.TavilySearchResults')
    def test_search_success(self, mock_tavily):
        mock_instance = mock_tavily.return_value
        mock_instance.invoke.return_value = "Snippets found"
        
        result = web.search("test query")
        self.assertEqual(result, "Snippets found")
        mock_instance.invoke.assert_called_with({"query": "test query"})

    @patch('neuro_agent.infrastructure.tools.web.requests.get')
    def test_read_page_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.content = b"<html><body><p>Hello World</p><script>bad</script></body></html>"
        mock_get.return_value = mock_response
        
        result = web.read_page("http://example.com")
        self.assertIn("Hello World", result)
        self.assertNotIn("bad", result) # Script should be removed

class TestDatabaseTools(unittest.TestCase):
    def setUp(self):
        os.environ['AWS_REGION'] = 'us-east-1'
        os.environ['DYNAMO_TABLE_TODOS'] = 'TestTodos'
        os.environ['DYNAMO_TABLE_PROFILES'] = 'TestProfiles'
        database._get_table.cache_clear()

    @patch('neuro_agent.infrastructure.tools.database.boto3.resource')
    def test_save_task(self, mock_boto):
        mock_table = MagicMock()
        mock_boto.return_value.Table.return_value = mock_table
        
        result = database.save_task("user_123", "Buy milk")
        self.assertIn("Tarea guardada correctamente", result)
        mock_table.put_item.assert_called()

    @patch('neuro_agent.infrastructure.tools.database.boto3.resource')
    def test_get_context(self, mock_boto):
        mock_table_profile = MagicMock()
        mock_table_todos = MagicMock()
        
        # Mocking separate table calls
        def side_effect(name):
            if name == 'TestProfiles': return mock_table_profile
            if name == 'TestTodos': return mock_table_todos
            return MagicMock()
            
        mock_boto.return_value.Table.side_effect = side_effect
        
        mock_table_profile.get_item.return_value = {'Item': {'name': 'Alice'}}
        mock_table_todos.query.return_value = {'Items': [{'task': 'Run'}]}
        
        result = database.get_context("user_123")
        self.assertEqual(result['profile']['name'], 'Alice')
        self.assertEqual(len(result['todos']), 1)

class TestDelegationTools(unittest.TestCase):
    def setUp(self):
        os.environ['AWS_REGION'] = 'us-east-1'
        os.environ['EXECUTOR_LAMBDA_ARN'] = 'arn:aws:lambda:us-east-1:123:function:executor'

    @patch('neuro_agent.infrastructure.tools.delegation.boto3.client')
    def test_delegate_task(self, mock_client):
        mock_lambda = mock_client.return_value
        mock_payload = MagicMock()
        mock_payload.read.return_value = b'{"body": "Task done"}'
        mock_lambda.invoke.return_value = {'Payload': mock_payload}
        
        result = delegation.delegate_task("user_123", "Compute X")
        self.assertEqual(result, "Task done")
        
if __name__ == '__main__':
    unittest.main()
