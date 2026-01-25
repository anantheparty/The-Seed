"""
CodeGenNode - 单一代码生成节点

接收玩家指令 + 游戏状态，直接生成可执行的 Python 代码。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..model import ModelAdapter, ModelResponse
from ..utils import LogManager

logger = LogManager.get_logger()


@dataclass
class CodeGenResult:
    """代码生成结果"""
    code: str
    raw_response: ModelResponse


CODEGEN_SYSTEM_PROMPT = """
You are a Python code generator for OpenRA game control.

Your job: Given a player command and game state, generate Python code that executes the command.

## Rules

1. Output RAW PYTHON CODE ONLY - no markdown fences, no explanation text.
2. Only use methods from [Available API] section.
3. DO NOT import anything.
4. DO NOT do file I/O, network, subprocess, threads, reflection, eval/exec.
5. Keep code simple and direct.

## Available Objects

- `api`: OpenRA midlayer API (MacroActions) - use this for all game actions
- `raw_api`: Low-level GameAPI (for advanced queries only)
- `logger`: For logging
- `Location`, `TargetsQueryParam`, `Actor`, etc.: Data models

## Key API Methods

- `api.deploy_mcv_and_wait(wait_time=1.0)` - Deploy MCV
- `api.ensure_can_produce_unit(unit_name)` - Ensure prerequisites for production
- `api.produce_wait(unit_name, count, auto_place_building=True)` - Produce units/buildings
- `api.query_actor(TargetsQueryParam(...))` - Query game actors
- `api.dispatch_attack(units, target)` - Send units to attack
- `api.dispatch_explore(units)` - Send units to explore
- `api.harvester_mine(harvester)` - Command harvester to mine

## Output Format

Your code MUST set `__result__` at the end:

```python
__result__ = {
    "success": True/False,
    "message": "描述执行结果",
    "observations": "观测到的信息（可选）"
}
```

## Example

Player command: "展开基地车，造一个电厂"

```python
try:
    api.deploy_mcv_and_wait(wait_time=1.0)
    logger.info("基地车已展开")
    
    if not api.ensure_can_produce_unit("电厂"):
        raise RuntimeError("无法建造电厂")
    api.produce_wait("电厂", 1, auto_place_building=True)
    logger.info("电厂建造完成")
    
    __result__ = {
        "success": True,
        "message": "已展开基地车并建造了电厂",
        "observations": ""
    }
except Exception as e:
    __result__ = {
        "success": False,
        "message": f"执行失败: {e}",
        "observations": ""
    }
```
"""


def build_codegen_user_prompt(
    command: str,
    game_state: str,
    api_rules: str,
    history: Optional[str] = None
) -> str:
    """构建用户 prompt"""
    parts = [
        "[Player Command]",
        command,
        "",
        "[Current Game State]",
        game_state,
        "",
        "[Available API]",
        api_rules,
    ]
    
    if history:
        parts.extend([
            "",
            "[Recent History]",
            history
        ])
    
    parts.extend([
        "",
        "Now generate Python code to execute the player's command.",
        "Output code only, no explanation."
    ])
    
    return "\n".join(parts)


class CodeGenNode:
    """
    单一代码生成节点
    
    职责：
    1. 接收玩家指令
    2. 结合游戏状态
    3. 生成可执行的 Python 代码
    """
    
    def __init__(self, model: ModelAdapter):
        self.model = model
    
    def generate(
        self,
        command: str,
        game_state: str,
        api_rules: str,
        history: Optional[str] = None
    ) -> CodeGenResult:
        """
        生成代码
        
        Args:
            command: 玩家指令
            game_state: 当前游戏状态
            api_rules: 可用的 API 文档
            history: 最近的执行历史（可选）
        
        Returns:
            CodeGenResult: 生成的代码和原始响应
        """
        user_prompt = build_codegen_user_prompt(
            command=command,
            game_state=game_state,
            api_rules=api_rules,
            history=history
        )
        
        logger.debug("CodeGenNode: generating code for command: %s", command)
        
        response = self.model.complete(
            system=CODEGEN_SYSTEM_PROMPT,
            user=user_prompt,
            metadata={"node": "codegen"}
        )
        
        # 清理代码（移除可能的 markdown 围栏）
        code = self._clean_code(response.text)
        
        logger.info("CodeGenNode: generated code length=%d", len(code))
        logger.debug("CodeGenNode: code=\n%s", code)
        
        return CodeGenResult(code=code, raw_response=response)
    
    def _clean_code(self, text: str) -> str:
        """清理代码，移除 markdown 围栏等"""
        if not text:
            return ""
        
        # 移除 ```python ... ``` 或 ``` ... ```
        cleaned = re.sub(
            r"^```(?:python)?\s*|\s*```$",
            "",
            text.strip(),
            flags=re.IGNORECASE | re.MULTILINE
        )
        
        return cleaned.strip()
