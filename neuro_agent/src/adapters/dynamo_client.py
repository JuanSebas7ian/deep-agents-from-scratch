import boto3
import uuid
from typing import Dict, Any
from langchain_core.tools import tool

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
profile_table = dynamodb.Table('UserProfiles')
todo_table = dynamodb.Table('UserTodos')

def fetch_context_from_dynamo(user_id: str) -> Dict[str, Any]:
    """
    Reads context for the Blackboard.
    CRITICAL: Fails loudly if DynamoDB is unreachable to prevent state corruption.
    """
    # Direct calls without try/except to allow Supervisor crash on DB failure
    profile_response = profile_table.get_item(Key={'user_id': user_id})
    profile = profile_response.get('Item', {})

    todos_response = todo_table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key('user_id').eq(user_id)
    )
    todos = todos_response.get('Items', [])
    
    return {"profile": profile, "todos": todos}

@tool
def write_task_to_dynamo(user_id: str, task_description: str) -> str:
    """Always use this tool to write a specific, atomic task to the database."""
    try:
        todo_table.put_item(
            Item={
                'user_id': user_id,
                'task_id': str(uuid.uuid4())[:8],
                'description': task_description,
                'status': 'pending'
            }
        )
        return f"Success: Task '{task_description}' saved."
    except Exception as e:
        return f"Error saving to DB: {e}"
