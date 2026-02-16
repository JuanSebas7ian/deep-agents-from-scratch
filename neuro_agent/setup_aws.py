import boto3
from botocore.exceptions import ClientError

def setup_aws_resources():
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    user_id = "user_neuro_001"
    
    print("--- Setting up NeuroAgent AWS Resources ---")
    
    # 1. UserProfiles
    profile_table = dynamodb.Table('UserProfiles')
    try:
        profile_table.put_item(Item={
            'user_id': user_id,
            'name': 'Alex',
            'diagnosis': 'ADHD',
            'preferences': 'Needs tasks broken down into very small steps. Gets overwhelmed by large lists.'
        })
        print("✅ UserProfiles: Mock profile injected.")
    except ClientError as e:
        print(f"❌ UserProfiles Error: {e}")

    # 2. UserTodos
    todo_table = dynamodb.Table('UserTodos')
    try:
        todo_table.put_item(Item={
            'user_id': user_id,
            'task_id': 't1', 
            'content': 'Clean the garage',
            'status': 'pending'
        })
        print("✅ UserTodos: Mock todo injected.")
    except ClientError as e:
        print(f"❌ UserTodos Error: {e}")
        
    # Check Checkpoints Table existence (cannot create from here easily without permissions, assuming exist)
    try:
        dynamodb.Table('LangGraphCheckpoints').load()
        print("✅ LangGraphCheckpoints: Table exists.")
    except ClientError:
        print("⚠️ LangGraphCheckpoints: Table NOT found. Please create it manually.")
        
if __name__ == "__main__":
    setup_aws_resources()
