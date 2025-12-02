from __future__ import annotations

from typing import Any, Dict

from ...utils import LogManager
from ..blackboard import Blackboard
from ..fsm import FSM, FSMState
from ..prompt import get_prompt
from .base import BaseNode, NodeOutput

logger = LogManager.get_logger()


class ActionGenNode(BaseNode):
    node_key = "action_gen"

    def _rt_contract(self, bb: Blackboard) -> str:
        return bb.gameapi_rules

    def run(self, fsm: FSM) -> NodeOutput:
        logger.info("ActionGenNode.run")
        bb = fsm.ctx.blackboard
        step = bb.plan[bb.step_index] or {}
        if not step:
            logger.warning("ActionGenNode: no current_step. Going back to PLAN.")
            return NodeOutput(next_state=FSMState.PLAN.value, payload={})
        logger.debug("ActionGenNode: current step=%r", step)

        prompt = get_prompt(self.node_key)
        user = prompt.build_user({
            "goal": fsm.ctx.goal,
            "step": step,
            "intel": bb.intel,
            "events": bb.events,
            "rt_contract": self._rt_contract(bb),
            "game_basic_state": bb.game_basic_state,
            "game_detail_state": bb.game_detail_state,
        })

        resp = self._complete(system=prompt.system, user=user, metadata={"node": self.node_key})
        logger.debug("ActionGenNode: response=\n```\n%s\n```", resp.text)
        python_script = (resp.text or "").strip()

        if not python_script:
            logger.warning("ActionGenNode: empty python from model. Back to PLAN.")
            return NodeOutput(next_state=FSMState.PLAN.value, payload={"error": "empty_python"})

        bb.python_script = python_script
        logger.info("ActionGenNode: python length=%d", len(python_script))
        exec_result = self._execute_code(python_script, fsm)
        logger.debug("ActionGenNode: execution result=%r", exec_result)
        bb.update_from_result(exec_result)

        next_state = exec_result.next_state
        payload: Dict[str, Any] = {
            "python": python_script,
            "execution": exec_result.to_dict(),
        }
        return NodeOutput(next_state=next_state, payload=payload)


   