from __future__ import annotations

from typing import Any

from ...utils import LogManager
from ..fsm import FSM, FSMState
from .base import BaseNode, NodeOutput

logger = LogManager.get_logger()


class NeedUserNode(BaseNode):
    """阻断流程并等待玩家在终端中确认。"""

    node_key = "need_user"

    def __init__(self) -> None:
        super().__init__(model=None)

    def _build_prompt(self, fsm: FSM) -> str:
        bb = fsm.ctx.blackboard
        reason = (
            bb.last_outcome.get("player_message")
            or bb.action_result.get("player_message")
            or bb.review.get("player_message")
            or ""
        )
        current_step = bb.current_step or {}
        return (
            "\n============================\n"
            "需要玩家介入：\n"
            f"- 当前目标: {fsm.ctx.goal}\n"
            f"- 当前步骤: {current_step}\n"
            f"- 最近提示: {reason or '（暂无具体提示）'}\n"
            "请在游戏中完成必要操作后，输入说明并回车以继续。\n"
            "如果无需说明可直接回车。\n"
            "============================\n"
            "> "
        )

    def run(self, fsm: FSM) -> NodeOutput:
        logger.warning("NeedUserNode.run: 等待玩家输入以继续流程。")
        prompt = self._build_prompt(fsm)
        try:
            user_note = input(prompt)
        except EOFError:
            user_note = ""
        user_note = (user_note or "").strip()

        if user_note:
            logger.info("NeedUserNode: 玩家输入=%s", user_note)
            fsm.ctx.blackboard.events.append(
                {
                    "type": "need_user_ack",
                    "message": user_note,
                }
            )
        else:
            logger.info("NeedUserNode: 玩家已确认（无附加说明）。")

        return NodeOutput(
            next_state=FSMState.PLAN.value,
            payload={
                "player_response": user_note,
            },
        )

