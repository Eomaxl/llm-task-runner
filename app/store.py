from datetime import datetime
import asyncio
from typing import Dict, Optional

from .models import Task

class InMemoryStore:
    """
    Simple store:
    - task: task_id -> Task
    - idempotency: idempotency_key -> task_id
    """
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._tasks: Dict[str, Task] = {}
        self._idemp: Dict[str, str] = {}
    
    async def create_or_get_task(self, task:Task) -> Task:
        async with self._lock:
            if task.idempotency_key:
                existing_id = self._idemp.get(task.idempotency_key)
                if existing_id and existing_id in self._tasks:
                    return self._tasks[existing_id]
                
            self._tasks[task.task_id] = task
            if task.idempotency_key:
                self._idemp[task.idempotency_key] = task.task_id
            return task
    
    async def get_task(self, task_id: str) -> Optional[Task]:
        async with self._lock:
            t = self._tasks.get(task_id)
            return t
        
    async def update_task(self, task: Task) -> None:
        async with self._lock:
            task.updated_at = datetime.utcnow()
            self._tasks[task.task_id] = task
