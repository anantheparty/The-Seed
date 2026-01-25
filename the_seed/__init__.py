"""
THE-Seed - 简化的游戏 AI 代码生成框架

新架构:
- CodeGenNode: 单一代码生成节点
- SimpleExecutor: 简化执行器
"""
from __future__ import annotations

# New simplified architecture (recommended)
from .core import (
    CodeGenNode,
    CodeGenResult,
    SimpleExecutor,
    ExecutorContext,
    ExecutionResult,
)

# Model & Utils (always available)
from .model import ModelResponse, ModelAdapter, ModelFactory
from .utils import LogManager, build_def_style_prompt

__all__ = [
    # New architecture
    "CodeGenNode",
    "CodeGenResult",
    "SimpleExecutor",
    "ExecutorContext",
    "ExecutionResult",
    # Model
    "ModelAdapter",
    "ModelResponse",
    "ModelFactory",
    # Utils
    "LogManager",
    "build_def_style_prompt",
]


# Legacy imports - lazy loaded for backward compatibility
def __getattr__(name: str):
    """Lazy import for legacy modules"""
    legacy_names = {
        "ActionGenNode", "BaseNode", "Blackboard", "CommitNode",
        "FSM", "FSMContext", "FSMState", "NodeFactory", "NodeOutput",
        "ObserveNode", "PlanNode", "ReviewNode", "NeedUserNode",
    }
    
    if name in legacy_names:
        import warnings
        warnings.warn(
            f"{name} is deprecated. Use new simplified architecture: "
            "CodeGenNode, SimpleExecutor, ExecutorContext",
            DeprecationWarning,
            stacklevel=2
        )
        from .core.legacy import (
            ActionGenNode, BaseNode, Blackboard, CommitNode,
            FSM, FSMContext, FSMState, NodeFactory, NodeOutput,
            ObserveNode, PlanNode, ReviewNode, NeedUserNode,
        )
        return locals()[name]
    
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
