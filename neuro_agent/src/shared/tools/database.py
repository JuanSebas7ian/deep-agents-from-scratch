import boto3
import os
import uuid
from functools import lru_cache
from typing import Dict, Any

# --- Private Adapter Logic (Oculta) ---
@lru_cache(maxsize=None)
def _get_table(env_var, default_name):
    dynamodb = boto3.resource('dynamodb', region_name=os.getenv('AWS_REGION', 'us-east-1'))
    return dynamodb.Table(os.getenv(env_var, default_name))

# --- Public Tools (Visible para el Agente) ---

def save_task(user_id: str, description: str) -> str:
    """
    TOOL: Guarda una nueva tarea en la base de datos.
    Uso: Cuando el usuario confirme que quiere recordar hacer algo.
    """
    try:
        table = _get_table('DYNAMO_TABLE_TODOS', 'UserTodos')
        task_id = str(uuid.uuid4())[:8]
        table.put_item(Item={
            'user_id': user_id, 
            'task_id': task_id, 
            'description': description, 
            'status': 'pending'
        })
        return f"Tarea guardada correctamente (ID: {task_id})."
    except Exception as e:
        return f"Error guardando tarea: {e}"

def get_context(user_id: str) -> Dict[str, Any]:
    """
    TOOL: Recupera todo lo que sabemos del usuario (Perfil + Tareas).
    Uso: Al iniciar la conversación o cuando necesites contexto fresco.
    """
    try:
        # Lectura paralela simulada (en realidad secuencial rápida)
        profile_table = _get_table('DYNAMO_TABLE_PROFILES', 'UserProfiles')
        todo_table = _get_table('DYNAMO_TABLE_TODOS', 'UserTodos')
        
        profile = profile_table.get_item(Key={'user_id': user_id}).get('Item', {})
        
        from boto3.dynamodb.conditions import Key
        todos_response = todo_table.query(
            KeyConditionExpression=Key('user_id').eq(user_id)
        )
        todos = todos_response.get('Items', [])
        
        return {"profile": profile, "todos": todos}
    except Exception:
        return {"profile": {}, "todos": []}
