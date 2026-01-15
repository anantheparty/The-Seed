from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from ..utils import LogManager

logger = LogManager.get_logger()


@dataclass
class ExecutionResult:
    success: bool
    next_state: str
    player_message: str
    observations: str
    next_step_hint: str
    raw_result: Dict[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "next_state": self.next_state,
            "player_message": self.player_message,
            "observations": self.observations,
            "next_step_hint": self.next_step_hint,
            "raw_result": self.raw_result,
            "error": self.error,
        }


class PythonActionExecutor:
    """执行 LLM 生成的 python 代码，并返回 __result__ 内容。"""

    REQUIRED_KEYS = {"next_state", "player_message", "observations", "next_step_hint"}

    def __init__(self, *, runtime_globals: Dict[str, Any] | None = None):
        self.runtime_globals = runtime_globals or {}

    def execute(self, code: str) -> ExecutionResult:
        logger.info("执行动作脚本，长度=%d", len(code))
        globals_dict: Dict[str, Any] = {
            "__builtins__": __builtins__,
            "logger": logger,
        }
        globals_dict.update(self.runtime_globals)

        try:
            exec(code, globals_dict, globals_dict)
        except Exception as exc:  # noqa: BLE001
            logger.exception("执行动作脚本失败")
            return ExecutionResult(
                success=False,
                next_state="REVIEW",
                player_message=f"python execution failed: {exc}",
                observations="",
                next_step_hint="execution_error",
                raw_result=None,
                error=str(exc),
            )

        result = globals_dict.get("__result__")
        if not isinstance(result, dict):
            logger.error("__result__ 缺失或格式错误")
            return ExecutionResult(
                success=False,
                next_state="REVIEW",
                player_message="missing __result__ dict",
                observations="",
                next_step_hint="missing_result",
                raw_result=None,
                error="missing_result",
            )

        missing = self.REQUIRED_KEYS - set(result.keys())
        if missing:
            logger.error("__result__ 缺少字段：%s", ", ".join(sorted(missing)))
            return ExecutionResult(
                success=False,
                next_state="REVIEW",
                player_message=f"__result__ missing keys: {sorted(missing)}",
                observations=str(result),
                next_step_hint="result_missing_keys",
                raw_result=result,
                error="result_missing_keys",
            )

        next_state = str(result.get("next_state", "") or "").upper()
        player_message = str(result.get("player_message", ""))
        observations = str(result.get("observations", ""))
        next_step_hint = str(result.get("next_step_hint", ""))

        logger.info("动作脚本完成，next_state=%s", next_state or "UNKNOWN")
        return ExecutionResult(
            success=True,
            next_state=next_state,
            player_message=player_message,
            observations=observations,
            next_step_hint=next_step_hint,
            raw_result=result,
            error=None,
        )

