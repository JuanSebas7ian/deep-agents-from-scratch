import boto3
import json

lambda_client = boto3.client('lambda', region_name='us-east-1')

def invoke_executor_lambda(user_id: str, explicit_instructions: str) -> str:
    """
    Driven Adapter: Synchronously invokes the remote Subagent Lambda.
    This provides true Compute Isolation.
    """
    payload = {
        "user_id": user_id,
        "explicit_instructions": explicit_instructions
    }
    
    try:
        response = lambda_client.invoke(
            FunctionName='NeuroAgent-Executor-Subagent-Prod',
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        result = json.loads(response['Payload'].read().decode('utf-8'))
        return result.get("body", "Executed successfully but without body response.")
    except Exception as e:
        return f"Network Error invoking remote subagent: {e}"
