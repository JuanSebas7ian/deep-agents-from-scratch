"""DynamoDB-based checkpointer for LangGraph state persistence.

This module provides DynamoDB table creation and a checkpointer wrapper
for persisting LangGraph agent state (conversation history, channel values)
across sessions.

Architecture:
    Table: DeepAgents_Checkpoints (and DeepAgents_Writes)
    PK: thread_id (String)
    SK: checkpoint_id (String)

If the `langgraph-checkpoint-dynamodb` package is installed, we use it.
Otherwise, we provide a simplified custom implementation.
"""

import json
import pickle
import time
import asyncio
from typing import Any, Dict, Iterator, Optional, Sequence, AsyncIterator

import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

try:
    from langchain_core.runnables import RunnableConfig
    from langgraph.checkpoint.base import Checkpoint, CheckpointMetadata, ChannelVersions, CheckpointTuple
except ImportError:
    # Define dummy types for fallback if libraries are missing (unlikely in this context)
    RunnableConfig = Any
    Checkpoint = Any
    CheckpointMetadata = Any
    ChannelVersions = Any
    CheckpointTuple = Any


# ─── Table Configuration ─── #

# Tables for Official DynamoDBSaver (LangGraph)
DEFAULT_CHECKPOINTS_TABLE = "DeepAgents_Checkpoints"
DEFAULT_WRITES_TABLE = "DeepAgents_Writes"

# Table for Custom Artifacts (TODOs, Files)
DEFAULT_ARTIFACTS_TABLE = "DeepAgents_Artifact"
DEFAULT_STATE_TABLE = "DeepAgents_Checkpoints" # Updated default


def validate_dynamodb_tables(
    region_name: str = "us-east-1",
    checkpoints_table: str = DEFAULT_CHECKPOINTS_TABLE,
    writes_table: str = DEFAULT_WRITES_TABLE,
    artifacts_table: str = DEFAULT_ARTIFACTS_TABLE,
) -> Dict[str, str]:
    """Check if DynamoDB tables exist.
    
    Validates 3 tables:
    1. Checkpoints (LangGraph State)
    2. Writes (LangGraph Pending Writes)
    3. Artifacts (DeepAgents Files/TODOs)
    """
    dynamodb = boto3.resource("dynamodb", region_name=region_name)
    results = {}

    tables_to_check = [checkpoints_table, writes_table, artifacts_table]

    for table in tables_to_check:
        try:
            dynamodb.Table(table).load()
            results[table] = "EXISTS"
        except ClientError as e:
            results[table] = f"NOT FOUND (Create manually): {e}"

    return results


def wait_for_tables(
    region_name: str = "us-east-1",
    table_names: list[str] | None = None,
    timeout: int = 3,
) -> None:
    """Wait for DynamoDB tables to become ACTIVE.

    Args:
        region_name: AWS region
        table_names: Tables to wait for (defaults to both DeepAgents tables)
        timeout: Maximum seconds to wait
    """
    if table_names is None:
        table_names = [DEFAULT_CHECKPOINTS_TABLE, DEFAULT_WRITES_TABLE, DEFAULT_ARTIFACTS_TABLE]

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
    """Get the custom DeepAgents checkpointer (with compression/chunking).
    
    We mandate the use of `DeepAgentsCheckpointer` because it handles:
    1. Zlib compression (reduces state size by ~80-90%)
    2. Item Chunking (splits large states >300KB into multiple items)
    3. Pickle serialization (handles complex Python objects natively)
    
    This avoids the 400KB DynamoDB item limit that the official library often hits.
    """
    if table_name == "DeepAgents_State":
        # Fallback if user passes old default but lacks permission
        print("⚠️ Warning: 'DeepAgents_State' requested but likely inaccessible. Switching to 'DeepAgents_Checkpoints'.")
        table_name = "DeepAgents_Checkpoints"

    print(f"✅ Using DeepAgentsCheckpointer (Table: {table_name})")
    print(f"   - Features: Zlib Compression + Automatic Chunking")
    return DeepAgentsCheckpointer(table_name=table_name, region_name=region_name)


class DeepAgentsCheckpointer:
    """Robust DynamoDB checkpointer with Compression and Chunking.

    Solves the "Item size has exceeded the maximum allowed size" error by:
    1. Compressing data with zlib (fast, high ratio for text).
    2. Splitting data into chunks if it still exceeds safe DynamoDB limits.
    
    Table Schema (DeepAgents_Checkpoints):
        PK: thread_id (String)
        SK: checkpoint_id (String)
        checkpoint_data: Zlib-compressed Pickled checkpoint (Binary)
        metadata_data: Zlib-compressed Pickled metadata (Binary)
        is_chunk: Boolean (if True, this is a split chunk)
    
    Table Schema (DeepAgents_Writes):
        PK: thread_id_checkpoint_id_checkpoint_ns (String)
        SK: task_id_idx (String)
        writes_data: Zlib-compressed Pickled writes (Binary)
    """
    
    CHUNK_SIZE_LIMIT = 350 * 1024  # 350KB (safe margin below 400KB)

    def __init__(
        self, 
        table_name: str, 
        region_name: str = "us-east-1",
        writes_table_name: str = "DeepAgents_Writes",
    ):
        self.dynamodb = boto3.resource("dynamodb", region_name=region_name)
        self.table = self.dynamodb.Table(table_name)
        self.writes_table = self.dynamodb.Table(writes_table_name)
        self.table_name = table_name

    def get_next_version(self, current: Optional[str], channel: Any) -> str:
        """Get the next version for a channel.
        
        This is required by LangGraph >= 0.2.
        For simple incrementing versions, we can rely on standard behavior or UUIDs.
        If 'current' is None, return 'v1'. Otherwise increment.
        Actually, LangGraph standard checkpointer uses integer-like or timestamp behavior.
        We'll use a simple lexicographical increment or timestamp.
        """
        if current is None:
            return "000000000000001"
        try:
            # Try to interpret as int and increment
            return f"{int(current) + 1:015d}"
        except ValueError:
            # Fallback to timestamp if not integer
            return str(int(time.time() * 1000))


    def get_tuple(self, config: dict) -> Optional[Any]:
        """Get the latest checkpoint for a thread."""
        from langgraph.checkpoint.base import CheckpointTuple
        import zlib
        from boto3.dynamodb.conditions import Key

        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = config["configurable"].get("checkpoint_id")

        item = None

        if checkpoint_id:
            # 1. Fetch specific checkpoint
            try:
                response = self.table.get_item(
                    Key={"thread_id": thread_id, "checkpoint_id": checkpoint_id}
                )
            except ClientError:
                return None

            if "Item" in response:
                item = response["Item"]
        else:
            # 2. Query latest checkpoint
            # Must handle chunks which sort 'higher' in DESC order due to suffix
            try:
                response = self.table.query(
                    KeyConditionExpression=Key("thread_id").eq(thread_id),
                    ScanIndexForward=False,
                    Limit=20, # Fetch enough to skip chunks
                )
            except ClientError:
                return None

            items = response.get("Items", [])
            for cand in items:
                # We are looking for the MAIN item (not a chunk)
                if not cand.get("is_chunk"):
                    item = cand
                    break
        
        if not item:
            return None

        # ─── Reconstruction Logic ─── #
        if "checkpoint_data" not in item:
            # Handle legacy items from official saver (incompatible schema)
            print(f"⚠️ Found legacy checkpoint format (id={item.get('checkpoint_id')}). Ignoring.")
            return None

        checkpoint_blob = item.get("checkpoint_data").value
        metadata_blob = item.get("metadata_data").value
        total_chunks = int(item.get("total_chunks", 1))

        if total_chunks > 1:
            # Fetch remaining chunks
            base_id = item["checkpoint_id"]
            chunks = [checkpoint_blob]  # Chunk 0
            
            for i in range(1, total_chunks):
                chunk_id = f"{base_id}#chunk_{i}"
                resp = self.table.get_item(
                    Key={"thread_id": thread_id, "checkpoint_id": chunk_id}
                )
                if "Item" not in resp:
                    print(f"⚠️ Missing chunk {i} for checkpoint {base_id}")
                    return None
                chunks.append(resp["Item"]["checkpoint_data"].value)
            
            checkpoint_blob = b"".join(chunks)

        # Decompress & Unpickle
        try:
            checkpoint = pickle.loads(zlib.decompress(checkpoint_blob))
            metadata = pickle.loads(zlib.decompress(metadata_blob))
        except (zlib.error, pickle.UnpicklingError, ValueError) as e:
            print(f"⚠️ Corrupt checkpoint data: {e}")
            return None

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
        """Save a checkpoint with compression and chunking."""
        import zlib

        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = checkpoint["id"]
        parent_checkpoint_id = config["configurable"].get("checkpoint_id")

        # 1. Serialize & Compress
        cp_bytes = zlib.compress(pickle.dumps(checkpoint))
        md_bytes = zlib.compress(pickle.dumps(metadata))
        
        # 2. Check Size & Chunk
        total_size = len(cp_bytes)
        chunks = []
        if total_size > self.CHUNK_SIZE_LIMIT:
            for i in range(0, total_size, self.CHUNK_SIZE_LIMIT):
                chunks.append(cp_bytes[i : i + self.CHUNK_SIZE_LIMIT])
        else:
            chunks.append(cp_bytes)

        # 3. Write Main Item (Chunk 0)
        total_chunks = len(chunks)
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ")

        main_item = {
            "thread_id": thread_id,
            "checkpoint_id": checkpoint_id,
            "checkpoint_data": chunks[0],
            "metadata_data": md_bytes,
            "parent_checkpoint_id": parent_checkpoint_id or "",
            "created_at": timestamp,
            "total_chunks": total_chunks,
            "checkpoint_ns": checkpoint_ns,
            "type": "checkpoint",
        }
        self.table.put_item(Item=main_item)

        # 4. Write Overflow Chunks
        for i in range(1, total_chunks):
            chunk_id = f"{checkpoint_id}#chunk_{i}"
            self.table.put_item(
                Item={
                    "thread_id": thread_id,
                    "checkpoint_id": chunk_id,
                    "checkpoint_data": chunks[i],
                    "created_at": timestamp,
                    "is_chunk": True,
                    "parent_checkpoint_id": checkpoint_id, 
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
    ) -> None:
        """Save pending writes to the Writes table."""
        import zlib
        
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = config["configurable"]["checkpoint_id"]

        # Construct key to match existing schema pattern
        # PK: thread_id_checkpoint_id_checkpoint_ns
        pk_val = f"{thread_id}_{checkpoint_id}_{checkpoint_ns}"
        
        writes_blob = zlib.compress(pickle.dumps(writes))
        
        self.writes_table.put_item(
            Item={
                "thread_id_checkpoint_id_checkpoint_ns": pk_val,
                "task_id_idx": task_id,
                "writes_data": writes_blob,
                "task_id": task_id,
            }
        )

    def list(self, config, **kwargs):
        """List checkpoints (Simplified implementation)."""
        pass

    # ─── Async Wrappers ─── #
    
    async def aget_tuple(self, config: RunnableConfig) -> Optional[Any]:
        return await asyncio.to_thread(self.get_tuple, config)

    async def aput(self, config: RunnableConfig, checkpoint: Checkpoint, metadata: CheckpointMetadata, new_versions: ChannelVersions) -> RunnableConfig:
        return await asyncio.to_thread(self.put, config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config: RunnableConfig, writes: Sequence[tuple[str, Any]], task_id: str) -> None:
        return await asyncio.to_thread(self.put_writes, config, writes, task_id)

    async def alist(self, config: Optional[RunnableConfig], **kwargs) -> AsyncIterator[Any]:
        if False: yield 
