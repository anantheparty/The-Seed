from __future__ import annotations

import json
from typing import Any, Dict

from ...utils import LogManager
from ..fsm import FSM, FSMState
from ..prompt import get_prompt
from .base import BaseNode, NodeOutput

logger = LogManager.get_logger()


class CommitNode(BaseNode):
    node_key = "commit"

    def run(self, fsm: FSM) -> NodeOutput:
        logger.info("CommitNode.run")
        prompt = get_prompt(self.node_key)
        bb = fsm.ctx.blackboard
        user = prompt.build_user({
            "goal": fsm.ctx.goal,
            "step": bb.current_step,
            "scratchpad": bb.scratchpad,
        })
        resp = self._complete(system=prompt.system, user=user, metadata={"node": self.node_key})

        data: Dict[str, Any]
        try:
            data = json.loads(resp.text)
        except Exception:
            logger.error("CommitNode: invalid JSON from model.")
            data = {
                "db_records": [],
                "player_message": "Commit failed: invalid model response.",
                "next_hint": {"observe_force": True},
            }

        bb.commit = data
        for record in data.get("db_records") or []:
            if record:
                fsm.write_db(record)

        logger.info("CommitNode: player_message=%s", data.get("player_message"))
        next_hint = data.get("next_hint") or {}
        next_state = FSMState.OBSERVE.value if next_hint.get("observe_force") else FSMState.PLAN.value
        return NodeOutput(next_state=next_state, payload={"commit": data})