from __future__ import annotations
from typing import Any, Dict, List, Literal, TypedDict
import re

ToolName = Literal["http_get", "calc"]

class PlannedStep(TypedDict):
    tool: ToolName
    args: Dict[str, Any]

class Planner:

    URL_RE = re.compile(r"(https?://\S+)", re.IGNORECASE)

    def plan(self, goal: str) -> List[PlannedStep]:
        steps: List[PlannedStep] = []
        m = self.URL_RE.search(goal)
        if m:
            steps.append({"tool":"http_get", "args": {"url": m.group(1)}})

        if "calc:" in goal.lower():
            expr = goal.split(":",1)[1].strip()
            steps.append({"tool":"calc", "args":{"expr":expr}})
        elif re.search(r"\bcalculate\b", goal.lower()):
            expr = goal.split("calculate", 1)[1].strip()
            if expr:
                steps.append({"tool":"calc", "args":{"expr":expr}})
        return steps

planner = Planner()    