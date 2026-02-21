"""DynamoDB-based checkpointer for LangGraph state persistence.

This module provides DynamoDB table creation and a checkpointer wrapper
for persisting LangGraph agent state (conversation history, channel values)
across sessions.

Architecture:
    Table: LangGraphCheckpoints (and LangGraphWrites)
    PK: thread_id (String)
    SK: checkpoint_id (String)

Implementation:
    - Uses Zlib compression to maximize storage efficiency.
    - Uses automated chunking for items > 350KB.
    - Uses Pickle serialization for full object fidelity.
"""

import json
import pickle
import time
import asyncio
import os
import zlib
from typing import Any, Dict, Iterator, Optional, Sequence, AsyncIterator

import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

try:
    from langchain_core.runnables import RunnableConfig
    from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint, CheckpointMetadata, ChannelVersions, CheckpointTuple
except ImportError:
    # Dummy types for fallback
    RunnableConfig = Any
    Checkpoint = Any
    CheckpointMetadata = Any
    ChannelVersions = Any
    CheckpointTuple = Any
    class BaseCheckpointSaver: pass


# ─── Table Configuration ─── #

DEFAULT_CHECKPOINTS_TABLE = os.getenv("DYNAMO_TABLE_CHECKPOINTS", "LangGraphCheckpoints")
DEFAULT_WRITES_TABLE = os.getenv("DYNAMO_TABLE_WRITES", "LangGraphWrites")


class ChunkedDynamoDBSaver(BaseCheckpointSaver):
    """Robust DynamoDB checkpointer with Compression and Chunking.

    Solves the "Item size has exceeded the maximum allowed size" error by:
    1. Compressing data with zlib (fast, high ratio for text).
    2. Splitting data into chunks if it still exceeds safe DynamoDB limits.
    
    Table Schema:
        PK: thread_id (String)
        SK: checkpoint_id (String)
        checkpoint_data: Zlib-compressed Pickled checkpoint (Binary)
        metadata_data: Zlib-compressed Pickled metadata (Binary)
        is_chunk: Boolean (if True, this is a split chunk)
    """
    
    CHUNK_SIZE_LIMIT = 350 * 1024  # 350KB (safe margin below 400KB)

    def __init__(
        self, 
        table_name: str = None, 
        region_name: str = "us-east-1",
        writes_table_name: str = None,
    ):
        super().__init__()
        self.table_name = table_name or DEFAULT_CHECKPOINTS_TABLE
        self.writes_table_name = writes_table_name or DEFAULT_WRITES_TABLE
        
        self.dynamodb = boto3.resource("dynamodb", region_name=region_name)
        self.table = self.dynamodb.Table(self.table_name)
        self.writes_table = self.dynamodb.Table(self.writes_table_name)

    def get_next_version(self, current: Optional[str], channel: Any) -> str:
        """Get the next version for a channel (Timestamp based)."""
        if current is None:
            return "000000000000001"
        try:
            # Try to interpret as int and increment
            return f"{int(current) + 1:015d}"
        except ValueError:
            # Fallback to timestamp if not integer
            return str(int(time.time() * 1000))


    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """Get the latest checkpoint for a thread."""
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
            # ScanIndexForward=False gives us descending order.
            # We fetch a batch to skip potential "chunk" items if they accidentally mix in
            try:
                response = self.table.query(
                    KeyConditionExpression=Key("thread_id").eq(thread_id),
                    ScanIndexForward=False,
                    Limit=20, 
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
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """Save a checkpoint with compression and chunking."""
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
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
    ) -> None:
        """Save pending writes to the Writes table."""
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = config["configurable"]["checkpoint_id"]

        # Construct key to match existing schema pattern
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

    def list(self, config: RunnableConfig, **kwargs) -> Iterator[CheckpointTuple]:
        """List checkpoints (Simplified implementation - Not filtering writes yet)."""
        pass

    # ─── Async Wrappers ─── #
    
    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        return await asyncio.to_thread(self.get_tuple, config)

    async def aput(self, config: RunnableConfig, checkpoint: Checkpoint, metadata: CheckpointMetadata, new_versions: ChannelVersions) -> RunnableConfig:
        return await asyncio.to_thread(self.put, config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config: RunnableConfig, writes: Sequence[tuple[str, Any]], task_id: str) -> None:
        return await asyncio.to_thread(self.put_writes, config, writes, task_id)

    async def alist(self, config: Optional[RunnableConfig], **kwargs) -> AsyncIterator[CheckpointTuple]:
        # Generator for async compatibility
        if False: yield 

# Alias for backward compatibility / ease of use
DynamoDBSaver = ChunkedDynamoDBSaver
