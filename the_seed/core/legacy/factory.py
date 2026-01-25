from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Dict, Mapping, Type

from ...config.manager import load_config
from ...config.schema import SeedConfig
from ...model import ModelAdapter, ModelFactory
from ...utils import LogManager
from .fsm import FSMState
from .node import (
    ActionGenNode,
    BaseNode,
    CommitNode,
    NeedUserNode,
    ObserveNode,
    PlanNode,
    ReviewNode,
)

logger = LogManager.get_logger()


@dataclass
class NodeModelBundle:
    template_name: str
    node_configs: Dict[str, Dict[str, Any]]


class NodeFactory:
    """
    Load Seed config and prepare per-node model definitions.

    The resulting ModelAdapter will automatically dispatch completions based on
    the node key (observe/plan/action_gen/review/commit).
    """

    NODE_ALIASES: Dict[FSMState, str] = {
        FSMState.OBSERVE: "observe",
        FSMState.PLAN: "plan",
        FSMState.ACTION_GEN: "action_gen",
        FSMState.REVIEW: "review",
        FSMState.COMMIT: "commit",
        FSMState.NEED_USER: "need_user",
    }

    def __init__(self, cfg: SeedConfig | None = None):
        self.cfg = cfg or load_config()
        logger.info("NodeFactory 加载配置完成。")
        self._nodes: Dict[str, BaseNode] = self._instantiate_nodes()

    def get_node(self, node_key: str | FSMState) -> BaseNode:
        normalized = self._normalize_node_key(node_key)
        node = self._nodes.get(normalized)
        if node is not None:
            return node
        raise KeyError(f"Unknown node '{node_key}'")

    def create_node(self, node_key: str | FSMState) -> BaseNode:
        """Backward-compatible alias that now simply returns/creates the node."""
        return self.get_node(node_key)

    # ---------------- Internal helpers ----------------
    def _build_model_adapters(self,node: str, config_id: str) -> ModelAdapter:
        return ModelFactory.build(node, self.cfg.model_templates[config_id])

    def _normalize_node_key(self, node_key: str | FSMState) -> str:
        if isinstance(node_key, FSMState):
            return self.NODE_ALIASES.get(node_key, node_key.value)
        return str(node_key).strip().lower()

    def _instantiate_nodes(self) -> Dict[str, BaseNode]:
        
        model_adapters = {
            "observe": self._build_model_adapters("observe", self.cfg.node_models.observe),
            "plan": self._build_model_adapters("plan", self.cfg.node_models.plan),
            "action_gen": self._build_model_adapters("action_gen", self.cfg.node_models.action),
            "review": self._build_model_adapters("review", self.cfg.node_models.review),
            "commit": self._build_model_adapters("commit", self.cfg.node_models.commit),
        }

        return {
            "observe": ObserveNode(model_adapters["observe"]),
            "plan": PlanNode(model_adapters["plan"]),
            "action_gen": ActionGenNode(model_adapters["action_gen"]),
            "review": ReviewNode(model_adapters["review"]),
            "commit": CommitNode(model_adapters["commit"]),
            "need_user": NeedUserNode(),
        }