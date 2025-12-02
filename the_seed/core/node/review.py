from __future__ import annotations

from typing import Any, Dict

from ...utils import LogManager
from ..fsm import FSM, FSMState
from ..prompt import get_prompt
from .base import BaseNode, NodeOutput

logger = LogManager.get_logger()


class ReviewNode(BaseNode):
    node_key = "review"

    def _local_precheck(self, py: str) -> Dict[str, Any]:
        """本地硬检查：先挡掉明显危险/不合规内容。"""
        issues = []
        lowered = py.lower()

        banned = ["import ", "open(", "subprocess", "socket", "requests", "urllib", "thread", "multiprocessing", "os.system"]
        for b in banned:
            if b in lowered:
                issues.append({"severity": "high", "kind": "safety", "msg": f"banned token detected: {b}"})

        if "__result__" not in py:
            issues.append({"severity": "high", "kind": "missing", "msg": "must set __result__"})

        return {"ok": len([i for i in issues if i["severity"] == "high"]) == 0, "issues": issues}

    def run(self, fsm: FSM) -> NodeOutput:
        logger.info("ReviewNode.run")
        bb = fsm.ctx.blackboard
        current_step = bb.current_step or {}
        last_code = bb.python_script or ""
        if not last_code.strip():
            logger.warning("ReviewNode: missing python. Back to ACTION_GEN.")
            return NodeOutput(next_state=FSMState.ACTION_GEN.value, payload={})

        prompt = get_prompt(self.node_key)
        user = prompt.build_user({
            "goal": fsm.ctx.goal,
            "step": current_step,
            "action_code": last_code,
            "action_result": bb.action_result,
            "scratchpad": bb.scratchpad,
        })
        resp = self._complete(system=prompt.system, user=user, metadata={"node": self.node_key})
        logger.debug("ReviewNode: response=\n```\n%s\n```", resp.text)
        patched_code = (resp.text or "").strip()

        if not patched_code:
            logger.error("ReviewNode: model returned empty python.")
            return NodeOutput(next_state=FSMState.PLAN.value, payload={"error": "empty_review_python"})

        pre = self._local_precheck(patched_code)
        bb.review = {"issues": pre["issues"], "patched": True}
        if not pre["ok"]:
            logger.warning("ReviewNode: patched python failed local precheck.")
            return NodeOutput(next_state=FSMState.PLAN.value, payload={"review": bb.review})

        bb.python_script = patched_code
        exec_result = self._execute_code(patched_code, fsm)
        bb.update_from_result(exec_result)

        next_state = self._map_next_state(exec_result.next_state, error=exec_result.error is not None)
        payload = {
            "python": patched_code,
            "execution": exec_result.to_dict(),
        }
        return NodeOutput(next_state=next_state, payload=payload)

    def _build_scratchpad(self, step: Dict[str, Any], exec_result) -> str:
        return (
            "[REVIEW PATCH]\n"
            f"skill={step.get('skill')} args={step.get('args')}\n"
            f"player_message={exec_result.player_message}\n"
            f"observations={exec_result.observations}\n"
            f"next_step_hint={exec_result.next_step_hint}"
        )