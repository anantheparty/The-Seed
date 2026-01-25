from __future__ import annotations

import json
from typing import Any, Dict

from ...utils import LogManager
from ..fsm import FSM, FSMState
from .base import BaseNode, NodeOutput

logger = LogManager.get_logger()


class ObserveNode(BaseNode):
    node_key = "observe"

    def run(self, fsm: FSM) -> NodeOutput:
        logger.info("ObserveNode.run")

        bb = fsm.ctx.blackboard

        # 1) 从内环取最小快照（内环未实现也要能降级）
        # try:
        #     intel = fsm.inner.get_intel_snapshot(force=False)
        #     logger.debug("Intel snapshot keys=%s", list(intel.keys()))
        # except Exception as e:
        #     logger.error("Failed to get intel snapshot: %s", e)
        #     intel = {"alerts": ["intel_snapshot_failed"]}
        intel = {}
        bb.intel = intel

        # 2) 让 LLM 决定是否需要“更深观察请求”（外环主线先把请求列出来）
        user_payload = {
            "goal": fsm.ctx.goal,
            "last_outcome": bb.last_outcome,
            "intel": bb.intel,
            "game_basic_state": bb.game_basic_state,
            "game_detail_state": bb.game_detail_state,
        }
        python_script = self._complete_python_script(fsm, prompt_key=self.node_key, payload=user_payload)
        exec_result = self._run_python(fsm, script=python_script, record_attr=None, log_prefix="ObserveNode")
        
        return NodeOutput(next_state=FSMState.PLAN.value, payload={"observe": exec_result.to_dict()})