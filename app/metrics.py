from __future__ import annotations
import asyncio
from typing import Dict

class Metrics:
    def __init__(self)-> None:
        self._lock = asyncio.Lock()
        self.counters: Dict[str, int] = {
            "task_created": 0,
            "task_running": 0,
            "tasks_succeeded": 0,
            "tasks_failed": 0,
            "tool_calls": 0,
            "tool_failures": 0,
            "llm_plans": 0,
        }


    async def inc(self, name: str, by: int = 1) -> None :
        async with self._lock:
            self.counters[name] = self.counters.get(name,0) + by

    async def dec(self, name: str, by: int = 1) -> None :
        await self.inc(name, -by)

    async def render_prometheus(self) -> str:
        async with self._lock:
            lines = []
            for k,v in self.counters.items():
                metric = f"llm_task_runner_{k}"
                lines.append(f"# TYPE {metric} counter")
                lines.append(f"{metric} {v}")
            return "\n".join(lines) + "\n"

metrics = Metrics()
      