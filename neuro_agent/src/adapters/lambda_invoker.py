import boto3
import json
import os
from functools import lru_cache
from botocore.config import Config

@lru_cache(maxsize=None)
def get_lambda_client():
    # Timeout agresivo de conexión y lectura
    config = Config(
        read_timeout=10,  # Máximo 10s esperando al Subagente
        connect_timeout=2,
        retries={'max_attempts': 0}
    )
    return boto3.client('lambda', region_name=os.getenv('AWS_REGION', 'us-east-1'), config=config)

def invoke_executor_lambda(user_id: str, explicit_instructions: str) -> str:
    """
    Driven Adapter: Synchronously invokes the remote Subagent Lambda.
    This provides true Compute Isolation.
    """
    client = get_lambda_client()
    arn = os.environ.get("EXECUTOR_LAMBDA_ARN")
    
    if not arn:
        return "Error: EXECUTOR_LAMBDA_ARN not configured."

    payload = {
        "user_id": user_id,
        "explicit_instructions": explicit_instructions
    }
    
    try:
        response = client.invoke(
            FunctionName=arn,
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        # Validar errores de la propia Lambda
        if "FunctionError" in response:
             error_payload = response['Payload'].read().decode('utf-8')
             raise Exception(f"Subagent Crashed: {error_payload}")
        
        result = json.loads(response['Payload'].read().decode('utf-8'))
        return result.get("body", "Executed successfully but without body response.")
    except client.exceptions.ReadTimeoutError:
        return "Error: The subagent took too long to respond. The action might still be processing."
    except Exception as e:
        return f"Network/System Error invoking remote subagent: {e}"
