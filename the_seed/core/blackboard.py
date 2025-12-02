from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..utils import LogManager
from .excution import ExecutionResult

logger = LogManager.get_logger()
@dataclass
class Blackboard:
    """集中存放运行过程中动态产生的共享数据。"""

    intel: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    scratchpad: str = ""
    
    # game state
    game_basic_state: str = ""
    game_detail_state: str = ""

    # plan
    plan: List[Dict[str, Any]] = field(default_factory=list)
    current_step: Dict[str, Any] = field(default_factory=dict)
    step_index: int = 0

    # action artifacts
    python_script: str = ""
    action_result: Dict[str, Any] = field(default_factory=dict)
    review: Dict[str, Any] = field(default_factory=dict)
    commit: Dict[str, Any] = field(default_factory=dict)

    # execution bookkeeping
    last_outcome: Dict[str, Any] = field(default_factory=dict)
    observation_requests: List[Dict[str, Any]] = field(default_factory=list)

    # persistence hooks / metrics hooks
    db_buffer: List[Dict[str, Any]] = field(default_factory=list)
    
    gameapi: Any = None
    gameapi_rules: str = ""

    def update_from_result(self, result: ExecutionResult):
        self.last_outcome = result.to_dict()
        self.scratchpad += self._build_scratchpad(result)
        self.action_result = result.to_dict()
        
    def _build_scratchpad(self, result: ExecutionResult) -> str:
        return (
            f"ActionNode observations={result.observations}\n"
            f"ActionNode next_step_hint={result.next_step_hint}\n"
        )