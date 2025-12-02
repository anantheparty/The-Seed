from __future__ import annotations

import json
from typing import Any, Dict, List

from ...utils import LogManager
from ..fsm import FSM, FSMState
from ..prompt import get_prompt
from .base import BaseNode, NodeOutput

logger = LogManager.get_logger()


class PlanNode(BaseNode):
    node_key = "plan"

    def _available_skills(self) -> List[str]:
        # [Todo] 未来接入你的 RTS 中间层 skills 列表
        return [
            "opening_economy",
            "ensure_buildings",
            "ensure_units",
            "scout_unexplored",
            "defend_base",
            "rally_production_to",
        ]

    def run(self, fsm: FSM) -> NodeOutput:
        logger.info("PlanNode.run")

        p = get_prompt(self.node_key)
        bb = fsm.ctx.blackboard
        user = p.build_user({
            "goal": fsm.ctx.goal,
            "intel": bb.intel,
            "events": bb.events,
            "game_basic_state": bb.game_basic_state,
            "game_detail_state": bb.game_detail_state,
        })

        resp = self._complete(system=p.system, user=user, metadata={"node": self.node_key})
        logger.debug("PlanNode: response=%r", resp.text)
        data: Dict[str, Any]
        try:
            data = json.loads(resp.text)
        except Exception:
            logger.error("PlanNode: invalid JSON from model.")
            data = {"plan_level": 1, "plan": [], "next": None, "why": "invalid_json", "assumptions": []}

        plan = data.get("plan", []) or []
        logger.debug("PlanNode: Set Plan To bb.plan=%r", plan)
        bb.plan = plan
        bb.step_index = 0
        bb.current_step = plan[0] if plan else {}
        assumptions = data.get("assumptions") or []
        bb.scratchpad+= f"\nPlanNode Assumptions: {assumptions}"
        logger.info("PlanNode: Plan generated=%s", plan)
        logger.info("PlanNode: Scratchpad=%s", bb.scratchpad)
        return NodeOutput(next_state=FSMState.ACTION_GEN.value, payload={"plan": data})