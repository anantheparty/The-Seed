"""
THE-Seed Core Module

新简化架构:
- CodeGenNode: 单一代码生成节点
- SimpleExecutor: 简化执行器
- ExecutorContext: 执行上下文
- ExecutionResult: 执行结果
"""
from __future__ import annotations

# New simplified architecture
from .codegen import CodeGenNode, CodeGenResult
from .executor import SimpleExecutor, ExecutorContext, ExecutionResult

__all__ = [
    # New architecture
    "CodeGenNode",
    "CodeGenResult", 
    "SimpleExecutor",
    "ExecutorContext",
    "ExecutionResult",
]


# Legacy imports - for backward compatibility only
# These are deprecated and will be removed in future versions
def __getattr__(name: str):
    """Lazy import for legacy modules"""
    legacy_imports = {
        "Blackboard": (".legacy.blackboard", "Blackboard"),
        "FSM": (".legacy.fsm", "FSM"),
        "FSMContext": (".legacy.fsm", "FSMContext"),
        "FSMState": (".legacy.fsm", "FSMState"),
        "NodeFactory": (".legacy.factory", "NodeFactory"),
        "BaseNode": (".legacy.node", "BaseNode"),
        "NodeOutput": (".legacy.node", "NodeOutput"),
        "ObserveNode": (".legacy.node", "ObserveNode"),
        "PlanNode": (".legacy.node", "PlanNode"),
        "ActionGenNode": (".legacy.node", "ActionGenNode"),
        "ReviewNode": (".legacy.node", "ReviewNode"),
        "CommitNode": (".legacy.node", "CommitNode"),
        "NeedUserNode": (".legacy.node", "NeedUserNode"),
    }
    
    if name in legacy_imports:
        import importlib
        import warnings
        warnings.warn(
            f"{name} is deprecated and will be removed. Use new simplified architecture.",
            DeprecationWarning,
            stacklevel=2
        )
        module_path, attr_name = legacy_imports[name]
        module = importlib.import_module(module_path, __package__)
        return getattr(module, attr_name)
    
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
