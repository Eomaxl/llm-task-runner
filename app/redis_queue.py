from __future__ import annotations
import redis.asyncio as redis


class RedisQueue:
    def __init__(self, r: redis.Redis, name: str = "queue:tasks"):
        self.r = r
        self.name = name

    async def enqueue(self, task_id: str) -> None:
        # LPUSH + BRPOP is a common pattern
        await self.r.lpush(self.name, task_id)

    async def dequeue_blocking(self, timeout_s:int = 0) -> str :
        item = await self.r.brpop(self.name, timeout= timeout_s)
        if item is None:
            raise TimeoutError("queue timeout")
        _,data = item
        return data.decode() if isinstance(data, (bytes, bytearray)) else str(data)