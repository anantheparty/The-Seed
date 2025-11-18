from __future__ import annotations
from typing import Any, Dict, List
import json

SYSTEM_HINT = """You are a game commander agent. You receive structured observations and a set of available tools (actions).
Your task: reason briefly, then output a JSON with keys: "thoughts" (string) and "tool_calls" (array of {{name, arguments}})."""

def build_agent_prompt(role_prompt: str, observation: Dict[str, Any], tools_schema: List[Dict[str, Any]]) -> str:
    # 统一把 observation + tools_schema embed 到 prompt（也可以改为 tool calling）
    prompt = {
        "system": SYSTEM_HINT,
        "role": role_prompt,
        "tools": tools_schema,
        "observation": observation
    }
    return json.dumps(prompt, ensure_ascii=False)