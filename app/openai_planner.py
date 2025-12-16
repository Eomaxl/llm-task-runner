from __future__ import annotations
from typing import Any, Dict, List, Literal, TypedDict

from openai import OpenAI
from .config import settings

ToolName = Literal["http_get","calc"]

class PlannedStep(TypedDict):
    tool: ToolName
    args: Dict[str, Any]
    
class OpenAIPlanner:
    def __init__(self)-> None:
        self.client = OpenAI()

    def _tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "name": "plan_steps",
                "description":"Create a short plan of tool calls to achieve the goal. Keep <= 5",
                "parameters": {
                    "type":"object",
                    "properties": {
                        "steps": {
                            "type":"array",
                            "items":{
                                "type":"object",
                                "properties": {
                                    "tool": {"type": "string","enum":["http_get","calc"]},
                                    "args": {"type": "object"},
                                },
                                "required": ["tool","args"],
                                "additionalProperties": False,
                            },
                        }
                    },
                    "required": ["steps"],
                    "additionalProperties": False,
                }
            }
        ]

    def plan(self, goal:str) -> List[PlannedStep]:
        prompt = (
            "You are a planner for a backend agent. \n"
            "Return only via tool calling `plan_steps`. \n"
            "Allowed tools: \n"
            "- http_get: {url}\n"
            "- calc: {expr} \n"
            "Constraints:\n"
            "- <=5 steps\n"
            "- If no tool is needed, return steps=[]\n"
            f"Goal: {goal}"
        )

        resp = self.client.responses.create(
            model =settings.openai_model,
            input=prompt,
            tools= self._tools(),
        )

        steps: List[PlannedStep] = []
        for item in resp.output:
            if getattr(item, "type", None) == "function_call" and getattr(item, "name", None) == "plan_steps":
                args = item.arguments
                import json
                payload = json.loads(args) if isinstance(args, str) else args
                steps = payload.get("steps",[])
                break
        
        return steps[:settings.max_steps]

planner = OpenAIPlanner()    