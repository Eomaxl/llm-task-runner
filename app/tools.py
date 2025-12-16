from __future__ import annotations
import ast
import httpx
from typing import Dict, Any

class ToolError(Exception):
    pass

async def http_get(url: str, timeout_s: float = 6.0) -> Dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=timeout_s, follow_max_redirects=True) as client:
            resp = await client.get(url)
            return {
                "status_code": resp.status_code,
                "header": dict(resp.headers),
                "text": resp.text[:4000],
            }
    except Exception as e:
        raise ToolError(f"http_get failed: {e}") from e

_ALLOWED_NODES = {
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow, ast.USub, ast.UAdd, ast.Load
}

def _validate_expr(node: ast.AST) -> None :
    for n in ast.walk(node):
        if type(n) not in _ALLOWED_NODES:
            raise ToolError(f"calc: disallowed syntax: {type(n).__name__}")
        
async def calc(expr: str ) -> Dict[str, Any]:
    try:
        parsed = ast.parse(expr, mode = "eval")
        _validate_expr(parsed)
        val = eval(compile(parsed, "<calc>", "eval"), {"__builtins__":{}},{})
        if not isinstance(val, (int, float)):
            raise ToolError("calc: expression did not produce a number")
        return {"value": float(val)}
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Calc failed : {e}") from e