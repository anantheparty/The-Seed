from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict

from ..utils import LogManager
# from inner_loop import InnerLoopRuntime
from .blackboard import Blackboard

logger = LogManager.get_logger()


class FSMState(str, Enum):
    OBSERVE = "observe"
    PLAN = "plan"
    ACTION_GEN = "action_gen"
    REVIEW = "review"
    COMMIT = "commit"
    STOP = "stop"
    DONE = "done"


@dataclass
class FSMContext:
    """
    FSM 在所有 Node 间传递的上下文。
    goal 等静态信息保留在 Context，自由变化的数据放进 Blackboard。
    """

    goal: str
    blackboard: Blackboard = field(default_factory=Blackboard)


class FSM:
    """
    外环 FSM：主线节点串行推进。
    [Todo] 后续可加并行旁路（memory curator / anti-drift/critic）。
    """

    def __init__(self, *, ctx: FSMContext):
        # self.inner = inner
        self.ctx = ctx
        self.state: FSMState = FSMState.OBSERVE

    def transition(self, nxt: str) -> None:
        logger.debug("FSM received transition request: %s", nxt)
        bb = self.ctx.blackboard
        if nxt.lower() == "RUN":
            bb.step_index += 1
            if bb.step_index >= len(bb.plan):
                nxt_state = FSMState.DONE.value
            else:
                nxt_state = FSMState.ACTION_GEN.value
                logger.info("FSM plan next step: %s", bb.plan[bb.step_index])
        else:
            nxt_state = FSMState(nxt.lower())
        logger.info("FSM transition: %s -> %s", self.state, nxt_state)
        self.state = nxt_state
        if bb.plan:
            idx = min(bb.step_index, len(bb.plan) - 1)
            bb.current_step = bb.plan[idx]
        else:
            bb.current_step = {}

    def write_db(self, record: Dict[str, Any]) -> None:
        logger.debug("FSM write_db buffered: %s", record.get("type", "unknown"))
        self.ctx.blackboard.db_buffer.append(record)
        # [Todo] flush to persistent store