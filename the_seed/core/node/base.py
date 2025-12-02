from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict

from ...model import ModelResponse, ModelAdapter
from ...utils import LogManager
from ..fsm import FSM, FSMState
from ..excution import PythonActionExecutor
from ..excution import ExecutionResult
import re

logger = LogManager.get_logger()


@dataclass(frozen=True)
class NodeOutput:
    next_state: str
    payload: Dict[str, Any] = None


class BaseNode(ABC):
    """
    所有主线节点共同基类。
    约束：
    - 每个节点只做自己的职责
    - 与 LLM 的交互通过 self.model（黑盒）
    """

    node_key: str

    def __init__(self, model: ModelAdapter):
        self.model = model

    @abstractmethod
    def run(self, fsm: FSM) -> NodeOutput: ...

    def _complete(self, *, system: str, user: str, metadata: Dict[str, Any]) -> ModelResponse:
        logger.debug("LLM complete for node=%s", self.node_key)
        return self.model.complete(system=system, user=user, metadata=metadata)

    def _resolve_gameapi(self, fsm: FSM) -> Any:
        return fsm.ctx.blackboard.gameapi

    def _map_next_state(self, requested: str, *, error: bool, default_success: FSMState = FSMState.PLAN, default_error: FSMState = FSMState.REVIEW) -> str:
        normalized = (requested or "").upper()
        mapping = {
            "RUN": FSMState.ACTION_GEN.value,
            "OBSERVE": FSMState.OBSERVE.value,
            "PLAN": FSMState.PLAN.value,
            "REVIEW": FSMState.REVIEW.value,
            "COMMIT": FSMState.COMMIT.value,
            "STOP": FSMState.STOP.value,
        }
        if normalized in mapping:
            return mapping[normalized]
        logger.warning("Unknown next_state '%s', fallback to %s", requested, default_error if error else default_success)
        return (default_error if error else default_success).value
    
    
    def _build_executor(self, fsm: FSM) -> PythonActionExecutor:
        bb = fsm.ctx.blackboard
        return PythonActionExecutor(runtime_globals=bb.runtime_globals)
    
    def _execute_code(self, code: str, fsm: FSM) -> ExecutionResult:
        bb = fsm.ctx.blackboard
        executor = self._build_executor(fsm)
        # 去掉任何 ``` 或 ```python 包住的部分
        clip_code = re.sub(
            r"^```(?:python)?\s*|\s*```$",
            "",
            code.strip(),
            flags=re.IGNORECASE | re.MULTILINE
        )

        return executor.execute(clip_code)