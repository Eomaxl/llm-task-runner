from __future__ import annotations
from typing import Optional, List
from datetime import datetime
import json

import redis.asyncio as redis

from .models import Task, StepRecord

class RedisStore:
    def __init__(self, r:redis.Redis):
        self.r = r

    def _task_key(self, task_id: str) -> str:
        return f"task:{task_id}"
    
    def _steps_key(self, task_id: str) -> str:
        return f"task:{task_id}:steps"
    
    def _idemp_key(self, idempotency_key: str) -> str:
        return f"idemp:{idempotency_key}"
    
    async def create_or_get_task(self, task: Task) -> Task:
        # Idempotency mapping (string -> task_id)
        if task.idempotency_key:
            existing_id = await self.r.get(self._idemp_key(task.idempotency_key))
            if existing_id:
                existing = await self.get_task(existing_id.decode())
                if existing:
                    return existing
        
        now = datetime.utcnow()
        task.created_at = now
        task.updated_at = now

        await self.r.hset(
            self._task_key(task_id),
            mapping={
                "task_id": task.task_id,
                "goal": task.goal,
                "status": task.status,
                "created_at": task.created_at.isoformat(),
                "updated_at": task.updated_at.isoformat(),
                "idempotency_key": task.idempotency_key or "",
                "result": task.result or "",
                "error": task.error or "",
            },
        )

        if task.idempotency_key:
            await self.r.set(self._idemp_key(task.idempotency_key), task.task_id)

        return task
    
    async def get_task(self, task_id: str) -> Optional[Task]:
        data = await self.r.hgetall(self._task_key(task_id))
        if not data:
            return None
        
        d = {k.decode(): v.decode() for k,v in data.items()}
        t = Task(
            task_id=d["task_id"],
            goal=d["goal"],
            status=d["status"],
            created_at=datetime.fromisoformat(d["created_at"])
            updated_at=datetime.fromisoformat(d["updated_at"])
            idempotency_key=d["idempotency_key"] or None,
            result = d["result"] or None,
            error = d["error"] or None,
            steps=[]
        )

        steps = await self.get_steps(task_id)
        t.steps = steps
        return t
    
    async def update_task_fields(
            self,
            task_id: str,
            *,
            status: Optional[str] = None,
            result: Optional[str] = None,
            error: Optional[str] = None,
    ) -> None:
        mapping = {"updated_at": datetime.utcnow().isoformat()}
        if status is not None:
            mapping["status"] = status
        if result is not None:
            mapping["result"] = result
        if error is not None:
            mapping["error"] = error
        await self.r.hset(self._task_key(task_id), mapping=mapping)
    
    async def append_step(self, task_id: str, step: StepRecord) -> None:
        await self.r.rpush(self._steps_key(task_id), step.model_dump_json())

    async def get_steps(self, task_id: str) -> List[StepRecord]:
        raw = await self.r.lrange(self._steps_key(task_id), 0, -1)
        steps: List[StepRecord] = []
        for b in raw:
            steps.append(StepRecord(**json.loads(b.decode())))
        return steps
            
