from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ...model import ModelResponse, ModelAdapter
from ...utils import LogManager
from ..fsm import FSM, FSMState
from ..excution import PythonActionExecutor
from ..excution import ExecutionResult
from ..prompt import get_prompt
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

    def __init__(self, model: Optional[ModelAdapter] = None):
        self.model = model

    @abstractmethod
    def run(self, fsm: FSM) -> NodeOutput: ...

    def _complete(self, *, system: str, user: str, metadata: Dict[str, Any]) -> ModelResponse:
        if not self.model:
            raise RuntimeError(f"Node '{self.node_key}' 未配置模型，无法调用 LLM。")
        logger.info("LLM complete for node=%s", self.node_key)
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
            "NEED_USER": FSMState.NEED_USER.value,
            "STOP": FSMState.STOP.value,
        }
        if normalized in mapping:
            return mapping[normalized]
        logger.warning("Unknown next_state '%s', fallback to %s", requested, default_error if error else default_success)
        return (default_error if error else default_success).value
    
    # ----- Shared helpers for LLM -> Python -> Execution flow -----
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

    def _complete_python_script(self, fsm: FSM, *, prompt_key: str, payload: Dict[str, Any]) -> str:
        prompt_def = get_prompt(prompt_key)
        user = prompt_def.build_user(payload)
        system_log = prompt_def.system.strip()
        user_log = user.strip()
        logger.debug("%s prompt system:\n%s", prompt_key, system_log)
        logger.debug("%s prompt user:\n%s", prompt_key, user_log)
        resp = self._complete(system=prompt_def.system, user=user, metadata={"node": prompt_key})
        script = (resp.text or "").strip()
        logger.info("%s: response=\n```\n%s\n```", prompt_key, resp.text)
        return script

    def _run_python(self, fsm: FSM, *, script: str, record_attr: Optional[str] = "python_script", log_prefix: Optional[str] = None) -> ExecutionResult:
        bb = fsm.ctx.blackboard
        if record_attr:
            setattr(bb, record_attr, script)
        prefix = log_prefix or self.node_key
        logger.info("%s: python length=%d", prefix, len(script))
        exec_result = self._execute_code(script, fsm)
        logger.info("%s: execution result=%r", prefix, exec_result)
        bb.update_from_result(exec_result)
        return exec_result

    def _standard_execution_payload(self, script: str, exec_result: ExecutionResult) -> Dict[str, Any]:
        return {
            "python": script,
            "execution": exec_result.to_dict(),
        }