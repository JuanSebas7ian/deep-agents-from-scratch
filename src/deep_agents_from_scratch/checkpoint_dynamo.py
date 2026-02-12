"""DynamoDB-based checkpointer for LangGraph state persistence.

This module provides DynamoDB table creation and a checkpointer wrapper
for persisting LangGraph agent state (conversation history, channel values)
across sessions.

Architecture:
    Table: DeepAgents_State
    PK: pk (String) — thread_id
    SK: sk (String) — checkpoint_id

If the `langgraph-checkpoint-dynamodb` package is installed, we use it.
Otherwise, we provide a simplified custom implementation.
"""

import json
import pickle
import time
from typing import Any, Iterator, Optional, Sequence

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError


# ─── Table Creation ─── #

DEFAULT_STATE_TABLE = "DeepAgents_State"
DEFAULT_ARTIFACTS_TABLE = "DeepAgents_Artifacts"


def create_dynamodb_tables(
    region_name: str = "us-east-1",
    state_table_name: str = DEFAULT_STATE_TABLE,
    artifacts_table_name: str = DEFAULT_ARTIFACTS_TABLE,
) -> dict[str, str]:
    """Create DynamoDB tables for DeepAgents state and artifacts.

    Creates two tables:
    1. DeepAgents_State — For LangGraph checkpoint persistence
    2. DeepAgents_Artifacts — For persistent TODOs and Files

    Args:
        region_name: AWS region
        state_table_name: Name for the state/checkpoint table
        artifacts_table_name: Name for the artifacts table

    Returns:
        Dict with table names and their status
    """
    dynamodb = boto3.client("dynamodb", region_name=region_name)
    results = {}

    # Table 1: State (Checkpoints)
    try:
        dynamodb.create_table(
            TableName=state_table_name,
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        results[state_table_name] = "CREATING"
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceInUseException":
            results[state_table_name] = "ALREADY_EXISTS"
        else:
            raise

    # Table 2: Artifacts (TODOs + Files)
    try:
        dynamodb.create_table(
            TableName=artifacts_table_name,
            KeySchema=[
                {"AttributeName": "thread_id", "KeyType": "HASH"},
                {"AttributeName": "artifact_id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "thread_id", "AttributeType": "S"},
                {"AttributeName": "artifact_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        results[artifacts_table_name] = "CREATING"
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceInUseException":
            results[artifacts_table_name] = "ALREADY_EXISTS"
        else:
            raise

    return results


def wait_for_tables(
    region_name: str = "us-east-1",
    table_names: list[str] | None = None,
    timeout: int = 60,
) -> None:
    """Wait for DynamoDB tables to become ACTIVE.

    Args:
        region_name: AWS region
        table_names: Tables to wait for (defaults to both DeepAgents tables)
        timeout: Maximum seconds to wait
    """
    if table_names is None:
        table_names = [DEFAULT_STATE_TABLE, DEFAULT_ARTIFACTS_TABLE]

    dynamodb = boto3.client("dynamodb", region_name=region_name)
    start = time.time()

    for table_name in table_names:
        while time.time() - start < timeout:
            try:
                resp = dynamodb.describe_table(TableName=table_name)
                status = resp["Table"]["TableStatus"]
                if status == "ACTIVE":
                    print(f"✅ {table_name}: ACTIVE")
                    break
                print(f"⏳ {table_name}: {status}...")
                time.sleep(2)
            except ClientError:
                time.sleep(2)
        else:
            print(f"⚠️ {table_name}: Timeout after {timeout}s")


# ─── Checkpointer ─── #

def get_checkpointer(
    table_name: str = DEFAULT_STATE_TABLE,
    region_name: str = "us-east-1",
):
    """Get a DynamoDB-backed checkpointer for LangGraph.

    Tries to use the official `langgraph-checkpoint-dynamodb` package first.
    If not installed, falls back to a simplified custom implementation.

    Args:
        table_name: DynamoDB table name for checkpoints
        region_name: AWS region

    Returns:
        A checkpointer compatible with LangGraph's compile(checkpointer=...)
    """
    # Try official package first
    try:
        from langgraph.checkpoint.dynamodb import DynamoDBSaver

        saver = DynamoDBSaver(
            table_name=table_name,
            region_name=region_name,
        )
        print(f"✅ Using official DynamoDBSaver (table: {table_name})")
        return saver
    except ImportError:
        pass

    # Try alternative package name
    try:
        from langgraph_checkpoint_dynamodb import DynamoDBSaver

        saver = DynamoDBSaver(
            table_name=table_name,
            region_name=region_name,
        )
        print(f"✅ Using langgraph_checkpoint_dynamodb (table: {table_name})")
        return saver
    except ImportError:
        pass

    # Fall back to custom implementation
    print(f"⚠️ Official DynamoDB checkpointer not installed.")
    print(f"   Install with: pip install langgraph-checkpoint-dynamodb")
    print(f"   Using SimpleDynamoDBSaver fallback (table: {table_name})")
    return SimpleDynamoDBSaver(table_name=table_name, region_name=region_name)


class SimpleDynamoDBSaver:
    """Simplified DynamoDB checkpointer for LangGraph.

    This is a fallback when `langgraph-checkpoint-dynamodb` is not installed.
    It provides basic checkpoint persistence using pickle serialization.

    For production use, install the official package:
        pip install langgraph-checkpoint-dynamodb

    Table Schema:
        pk (String, HASH): thread_id
        sk (String, RANGE): checkpoint_ns#checkpoint_id
        checkpoint_data (Binary): Pickled checkpoint
        metadata_data (Binary): Pickled metadata
        parent_checkpoint_id (String): Parent checkpoint reference
        created_at (String): ISO timestamp
    """

    def __init__(self, table_name: str, region_name: str = "us-east-1"):
        self.dynamodb = boto3.resource("dynamodb", region_name=region_name)
        self.table = self.dynamodb.Table(table_name)
        self.table_name = table_name

    def get_tuple(self, config: dict) -> Optional[Any]:
        """Get the latest checkpoint for a thread."""
        from langgraph.checkpoint.base import CheckpointTuple

        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = config["configurable"].get("checkpoint_id")

        if checkpoint_id:
            sk = f"{checkpoint_ns}#{checkpoint_id}"
            try:
                response = self.table.get_item(
                    Key={"pk": thread_id, "sk": sk}
                )
            except ClientError:
                return None

            if "Item" not in response:
                return None
            item = response["Item"]
        else:
            # Get latest checkpoint
            try:
                response = self.table.query(
                    KeyConditionExpression=(
                        Key("pk").eq(thread_id)
                        & Key("sk").begins_with(f"{checkpoint_ns}#")
                    ),
                    ScanIndexForward=False,
                    Limit=1,
                )
            except ClientError:
                return None

            items = response.get("Items", [])
            if not items:
                return None
            item = items[0]

        checkpoint = pickle.loads(item["checkpoint_data"].value)
        metadata = pickle.loads(item["metadata_data"].value)
        parent_id = item.get("parent_checkpoint_id")

        parent_config = None
        if parent_id:
            parent_config = {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": parent_id,
                }
            }

        return CheckpointTuple(
            config={
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": checkpoint["id"],
                }
            },
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config=parent_config,
        )

    def put(
        self,
        config: dict,
        checkpoint: dict,
        metadata: dict,
        new_versions: dict,
    ) -> dict:
        """Save a checkpoint."""
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = checkpoint["id"]
        parent_checkpoint_id = config["configurable"].get("checkpoint_id")

        sk = f"{checkpoint_ns}#{checkpoint_id}"

        self.table.put_item(
            Item={
                "pk": thread_id,
                "sk": sk,
                "checkpoint_data": pickle.dumps(checkpoint),
                "metadata_data": pickle.dumps(metadata),
                "parent_checkpoint_id": parent_checkpoint_id or "",
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        )

        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        }

    def put_writes(
        self,
        config: dict,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        """Save pending writes (simplified — stores with checkpoint)."""
        # Simplified: writes stored separately keyed by checkpoint
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = config["configurable"]["checkpoint_id"]

        sk = f"writes#{checkpoint_ns}#{checkpoint_id}#{task_id}"

        self.table.put_item(
            Item={
                "pk": thread_id,
                "sk": sk,
                "writes_data": pickle.dumps(writes),
                "task_id": task_id,
                "task_path": task_path,
            }
        )

    def list(
        self,
        config: Optional[dict],
        *,
        filter: Optional[dict] = None,
        before: Optional[dict] = None,
        limit: Optional[int] = None,
    ) -> Iterator[Any]:
        """List checkpoints for a thread."""
        from langgraph.checkpoint.base import CheckpointTuple

        if config is None:
            return

        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")

        query_kwargs = {
            "KeyConditionExpression": (
                Key("pk").eq(thread_id)
                & Key("sk").begins_with(f"{checkpoint_ns}#")
            ),
            "ScanIndexForward": False,
        }
        if limit:
            query_kwargs["Limit"] = limit

        try:
            response = self.table.query(**query_kwargs)
        except ClientError:
            return

        for item in response.get("Items", []):
            if item["sk"].startswith("writes#"):
                continue
            checkpoint = pickle.loads(item["checkpoint_data"].value)
            metadata = pickle.loads(item["metadata_data"].value)

            yield CheckpointTuple(
                config={
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": checkpoint["id"],
                    }
                },
                checkpoint=checkpoint,
                metadata=metadata,
            )

    def delete_thread(self, thread_id: str) -> None:
        """Delete all checkpoints for a thread."""
        response = self.table.query(
            KeyConditionExpression=Key("pk").eq(thread_id)
        )

        with self.table.batch_writer() as batch:
            for item in response.get("Items", []):
                batch.delete_item(Key={"pk": item["pk"], "sk": item["sk"]})
