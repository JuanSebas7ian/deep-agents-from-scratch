import boto3
import pickle
import asyncio
import base64
from typing import Optional, Dict, Any, Iterator, AsyncIterator, Sequence
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    ChannelVersions,
    WRITES_IDX_MAP,
    get_checkpoint_id,
)
from langchain_core.runnables import RunnableConfig
from boto3.dynamodb.conditions import Key, Attr
import time
import random

class DynamoDBSaver(BaseCheckpointSaver):
    """
    Hybrid (Sync/Async) Checkpointer using AWS DynamoDB.
    Supports app.invoke() and app.astream() including intermediate writes.
    """

    def __init__(self, table_name: str, region_name: str = "us-east-1"):
        super().__init__()
        self.dynamodb = boto3.resource('dynamodb', region_name=region_name)
        self.table = self.dynamodb.Table(table_name)

    # --- SÍNCRONO (Sync) ---

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """Synchronous retrieval of checkpoint + pending writes."""
        thread_id = config["configurable"]["thread_id"]
        # checkpoint_id from config (if present)
        config_checkpoint_id = get_checkpoint_id(config)
        
        checkpoint_item = None
        
        try:
            if config_checkpoint_id:
                # Direct get
                response = self.table.get_item(Key={'thread_id': thread_id, 'checkpoint_id': config_checkpoint_id})
                checkpoint_item = response.get('Item')
            else:
                # Get latest checkpoint (scan index forward=False)
                # We need to filter out 'writes' which have a different SK pattern if we store them in same table
                # Strategy: Checkpoints have simple numeric/uuid IDs. Writes have "write#..." prefix?
                # Actually, standard CheckpointID is a UUID or timestamp. 
                # Let's assume standard Checkpoint IDs don't start with "write#".
                response = self.table.query(
                    KeyConditionExpression=Key('thread_id').eq(thread_id),
                    ScanIndexForward=False, 
                    Limit=1
                )
                items = response.get('Items', [])
                if items:
                    # Ensure we didn't get a write record by accident if they share the table
                    # We should filter safely.
                    # Current strategy: Store writes with SK "write#{checkpoint_id}#{task_id}#{idx}"
                    # Checkpoints have SK "{checkpoint_id}"
                    # If we sort, "write#" comes after most UUIDs/timestamps? 
                    # Actually better to query specifically.
                    # For simplicity, if we mix types, we might need a GSI or filter.
                    # But typically get_tuple starts by finding the *latest checkpoint*.
                    # Let's iterate until we find a real checkpoint, not a write.
                    # (Optimally, writes should be in a separate table or GSI, but let's filter here)
                    for item in items:
                        if not item['checkpoint_id'].startswith("write#"):
                            checkpoint_item = item
                            break
                    # If singular query didn't find one (e.g. only writes exist?), might need loop.
                    # But usually writes are associated with a checkpoint.
            
            if not checkpoint_item:
                return None

            checkpoint_id = checkpoint_item['checkpoint_id']
            
            # Now fetch PENDING WRITES for this checkpoint
            # Writes are stored with SK starting with "write#{checkpoint_id}"
            writes_response = self.table.query(
                KeyConditionExpression=Key('thread_id').eq(thread_id) & Key('checkpoint_id').begins_with(f"write#{checkpoint_id}")
            )
            writes_items = writes_response.get('Items', [])
            
            pending_writes = []
            for item in writes_items:
                # item structure: {thread_id, checkpoint_id (write#...), task_id, channel, value, task_path}
                # We need to reconstruct (task_id, channel, value)
                val = pickle.loads(item['value'].value)
                pending_writes.append((item['task_id'], item['channel'], val))

            return self._parse_item(checkpoint_item, thread_id, pending_writes)
            
        except Exception as e:
            print(f"DynamoDB Sync Get Error: {e}")
        return None

    def list(self, config: RunnableConfig, **kwargs) -> Iterator[CheckpointTuple]:
        """Synchronous listing."""
        thread_id = config["configurable"]["thread_id"]
        limit = kwargs.get("limit", 10)
        
        try:
            # Query table, filtering out writes if possible or in loop
            # This naive implementation fetches everything and filters python-side
            # For production, use a GSI for CheckpointsOnly
            response = self.table.query(
                KeyConditionExpression=Key('thread_id').eq(thread_id),
                ScanIndexForward=False,
                Limit=limit * 5 # Fetch more to account for writes
            )
            
            count = 0
            for item in response.get('Items', []):
                if item['checkpoint_id'].startswith('write#'):
                    continue
                if count >= limit:
                    break
                yield self._parse_item(item, thread_id)
                count += 1
                
        except Exception as e:
            print(f"DynamoDB Sync List Error: {e}")

    def put(self, config: RunnableConfig, checkpoint: Checkpoint, metadata: CheckpointMetadata, new_versions: ChannelVersions) -> RunnableConfig:
        """Synchronous save checkpoint."""
        thread_id = config["configurable"]["thread_id"]
        checkpoint_id = checkpoint["id"]
        try:
            self.table.put_item(
                Item={
                    'thread_id': thread_id,
                    'checkpoint_id': checkpoint_id,
                    'checkpoint': boto3.dynamodb.types.Binary(pickle.dumps(checkpoint)),
                    'metadata': boto3.dynamodb.types.Binary(pickle.dumps(metadata)),
                    'parent_checkpoint_id': config["configurable"].get("checkpoint_id") # optional
                }
            )
        except Exception as e:
            print(f"DynamoDB Sync Put Error: {e}")

        return {"configurable": {"thread_id": thread_id, "checkpoint_id": checkpoint_id}}

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        """Synchronous save intermediate writes."""
        thread_id = config["configurable"]["thread_id"]
        checkpoint_id = config["configurable"]["checkpoint_id"]
        
        try:
            with self.table.batch_writer() as batch:
                for idx, (channel, value) in enumerate(writes):
                    # Sort Key: write#{checkpoint_id}#{task_id}#{idx}
                    # This ensures uniqueness and grouping by checkpoint
                    sk = f"write#{checkpoint_id}#{task_id}#{idx}"
                    
                    batch.put_item(
                        Item={
                            'thread_id': thread_id,
                            'checkpoint_id': sk,
                            'task_id': task_id,
                            'channel': channel,
                            'task_path': task_path,
                            'value': boto3.dynamodb.types.Binary(pickle.dumps(value))
                        }
                    )
        except Exception as e:
            print(f"DynamoDB Sync Put Writes Error: {e}")

    # --- ASYNC WRAPPERS (via asyncio.to_thread) ---

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        return await asyncio.to_thread(self.get_tuple, config)

    async def aput(self, config: RunnableConfig, checkpoint: Checkpoint, metadata: CheckpointMetadata, new_versions: ChannelVersions) -> RunnableConfig:
        return await asyncio.to_thread(self.put, config, checkpoint, metadata, new_versions)

    async def alist(self, config: RunnableConfig, **kwargs) -> AsyncIterator[CheckpointTuple]:
        items = await asyncio.to_thread(lambda: list(self.list(config, **kwargs)))
        for item in items:
            yield item

    async def aput_writes(self, config: RunnableConfig, writes: Sequence[tuple[str, Any]], task_id: str, task_path: str = "") -> None:
        return await asyncio.to_thread(self.put_writes, config, writes, task_id, task_path)
    
    def get_next_version(self, current: str | None, channel: Any) -> str:
        if current is None:
            current_v = 0
        elif isinstance(current, int):
            current_v = current
        else:
            current_v = int(current.split(".")[0])
        next_v = current_v + 1
        next_h = random.random()
        return f"{next_v:032}.{next_h:016}"

    # --- HELPER ---
    
    def _parse_item(self, item, thread_id, pending_writes=None) -> CheckpointTuple:
        """Deserialize DynamoDB item to CheckpointTuple."""
        ckpt = pickle.loads(item['checkpoint'].value if hasattr(item['checkpoint'], 'value') else item['checkpoint'])
        meta = pickle.loads(item['metadata'].value if hasattr(item['metadata'], 'value') else item['metadata'])
        
        return CheckpointTuple(
            config={
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_id": item["checkpoint_id"],
                    "checkpoint_ns": "" # Default
                }
            },
            checkpoint=ckpt,
            metadata=meta,
            parent_config={
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_id": item.get("parent_checkpoint_id"),
                }
            } if item.get("parent_checkpoint_id") else None,
            pending_writes=pending_writes or []
        )
