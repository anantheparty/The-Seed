from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, TypedDict

# —— 游戏无关的抽象协议 ——

@dataclass
class ActionParamSpec:
    name: str
    type: str         # "int" | "str" | "float" | "bool" | "object" | "array"
    required: bool = True
    desc: str = ""

@dataclass
class ActionSpec:
    name: str
    desc: str
    params: List[ActionParamSpec]
    returns: Optional[str] = None  # 描述返回值
    # 由游戏侧适配：callable(context, **kwargs) -> Any
    impl: Optional[Callable[..., Any]] = None  # 运行期注入

@dataclass
class ObservationSpec:
    name: str
    desc: str

@dataclass
class EventSpec:
    name: str
    desc: str

# —— 运行时结构 —— 
class EnvObservation(TypedDict, total=False):
    # 由游戏侧填充的结构化观测（示例字段）
    timestamp: float
    screen: Dict[str, Any]
    base: Dict[str, Any]
    visible_units: List[Dict[str, Any]]
    control_points: List[Dict[str, Any]]
    custom: Dict[str, Any]     # 任意扩展

@dataclass
class ToolCall:
    name: str
    arguments: Dict[str, Any]

@dataclass
class AgentDecision:
    # 通过 LLM 得到的“要执行的动作序列”
    tool_calls: List[ToolCall] = field(default_factory=list)
    thoughts: str = ""  # 可选：模型自述，便于调试/回放

@dataclass
class TickContext:
    tick_id: int
    observation: EnvObservation