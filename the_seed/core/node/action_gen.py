from __future__ import annotations

from typing import Any, Dict

from ...utils import LogManager
from ..blackboard import Blackboard
from ..fsm import FSM, FSMState
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
        logger.info("ActionGenNode: current step=%r", step)

        user_payload = {
            "goal": fsm.ctx.goal,
            "step": step,
            "intel": bb.intel,
            "events": bb.events,
            "rt_contract": self._rt_contract(bb),
            "game_basic_state": bb.game_basic_state,
            "game_detail_state": bb.game_detail_state,
        }
        python_script = self._complete_python_script(fsm, prompt_key=self.node_key, payload=user_payload)

        if not python_script:
            logger.warning("ActionGenNode: empty python from model. Back to PLAN.")
            return NodeOutput(next_state=FSMState.PLAN.value, payload={"error": "empty_python"})

        exec_result = self._run_python(fsm, script=python_script, record_attr="python_script", log_prefix="ActionGenNode")

        payload = self._standard_execution_payload(python_script, exec_result)
        return NodeOutput(next_state=exec_result.next_state, payload=payload)


   