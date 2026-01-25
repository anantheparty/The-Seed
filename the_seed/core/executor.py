"""
SimpleExecutor - 简化的执行器

处理整个流程：观测 → 代码生成 → 执行
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ..utils import LogManager
from .codegen import CodeGenNode, CodeGenResult

logger = LogManager.get_logger()


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    message: str
    observations: str = ""
    code: str = ""
    error: Optional[str] = None
    raw_result: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "observations": self.observations,
            "code": self.code,
            "error": self.error,
            "raw_result": self.raw_result,
        }


@dataclass
class ExecutorContext:
    """执行器上下文"""
    # API 对象
    api: Any = None
    raw_api: Any = None
    
    # API 文档
    api_rules: str = ""
    
    # 运行时全局变量（传递给 exec）
    runtime_globals: Dict[str, Any] = field(default_factory=dict)
    
    # 观测函数
    observe_fn: Optional[Callable[[], str]] = None
    
    # 执行历史
    history: List[Dict[str, Any]] = field(default_factory=list)
    max_history: int = 5


class SimpleExecutor:
    """
    简化的执行器
    
    流程：
    1. 观测游戏状态
    2. 调用 CodeGenNode 生成代码
    3. 执行代码
    4. 返回结果
    """
    
    def __init__(self, codegen: CodeGenNode, ctx: ExecutorContext):
        self.codegen = codegen
        self.ctx = ctx
    
    def run(self, command: str) -> ExecutionResult:
        """
        执行玩家指令
        
        Args:
            command: 玩家指令
        
        Returns:
            ExecutionResult: 执行结果
        """
        logger.info("SimpleExecutor: processing command: %s", command)
        
        # 1. 观测游戏状态
        game_state = self._observe()
        logger.info("SimpleExecutor: game state observed")
        
        # 2. 构建历史上下文
        history_text = self._build_history_text()
        
        # 3. 生成代码
        try:
            gen_result = self.codegen.generate(
                command=command,
                game_state=game_state,
                api_rules=self.ctx.api_rules,
                history=history_text
            )
        except Exception as e:
            logger.error("SimpleExecutor: code generation failed: %s", e)
            return ExecutionResult(
                success=False,
                message=f"代码生成失败: {e}",
                error=str(e)
            )
        
        if not gen_result.code.strip():
            logger.warning("SimpleExecutor: empty code generated")
            return ExecutionResult(
                success=False,
                message="LLM 返回了空代码",
                error="empty_code"
            )
        
        # 4. 执行代码
        exec_result = self._execute_code(gen_result.code)
        
        # 5. 记录历史
        self._record_history(command, gen_result.code, exec_result)
        
        return exec_result
    
    def _observe(self) -> str:
        """观测游戏状态"""
        if self.ctx.observe_fn:
            try:
                return self.ctx.observe_fn()
            except Exception as e:
                logger.error("SimpleExecutor: observe failed: %s", e)
                return f"观测失败: {e}"
        return "（无游戏状态）"
    
    def _build_history_text(self) -> Optional[str]:
        """构建历史文本"""
        if not self.ctx.history:
            return None
        
        lines = []
        for i, h in enumerate(self.ctx.history[-self.ctx.max_history:], 1):
            lines.append(f"{i}. Command: {h.get('command', '')}")
            lines.append(f"   Result: {h.get('success', False)} - {h.get('message', '')}")
        
        return "\n".join(lines)
    
    def _execute_code(self, code: str) -> ExecutionResult:
        """执行生成的代码"""
        logger.info("SimpleExecutor: executing code, length=%d", len(code))
        
        # 构建执行环境
        globals_dict: Dict[str, Any] = {
            "__builtins__": __builtins__,
            "logger": logger,
        }
        globals_dict.update(self.ctx.runtime_globals)
        
        try:
            exec(code, globals_dict, globals_dict)
        except Exception as e:
            logger.exception("SimpleExecutor: code execution failed")
            return ExecutionResult(
                success=False,
                message=f"代码执行失败: {e}",
                code=code,
                error=str(e)
            )
        
        # 提取结果
        result = globals_dict.get("__result__")
        
        if not isinstance(result, dict):
            logger.error("SimpleExecutor: __result__ missing or invalid")
            return ExecutionResult(
                success=False,
                message="代码未设置 __result__ 或格式错误",
                code=code,
                error="missing_result"
            )
        
        success = bool(result.get("success", False))
        message = str(result.get("message", ""))
        observations = str(result.get("observations", ""))
        
        logger.info("SimpleExecutor: execution complete, success=%s", success)
        
        return ExecutionResult(
            success=success,
            message=message,
            observations=observations,
            code=code,
            raw_result=result
        )
    
    def _record_history(
        self,
        command: str,
        code: str,
        result: ExecutionResult
    ) -> None:
        """记录执行历史"""
        self.ctx.history.append({
            "command": command,
            "code": code,
            "success": result.success,
            "message": result.message,
        })
        
        # 保持历史长度
        while len(self.ctx.history) > self.ctx.max_history * 2:
            self.ctx.history.pop(0)
